import os
import asyncio
import logging
from collections import defaultdict, deque

from dotenv import load_dotenv

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from rag_engine import (
    load_agent,
    answer_question,
    get_greeting,
)


# ============================================================
# CONFIGURAÇÃO
# ============================================================

load_dotenv()


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURAÇÕES DA CONVERSA
# ============================================================

MAX_HISTORY_MESSAGES = 10

MAX_TELEGRAM_MESSAGE_LENGTH = 4096


# ============================================================
# MEMÓRIA DAS CONVERSAS
# ============================================================

conversation_memory = defaultdict(
    lambda: deque(
        maxlen=MAX_HISTORY_MESSAGES
    )
)


# ============================================================
# CARREGAMENTO DO AGENTE
# ============================================================

logger.info("Carregando agente RAG...")

qa_chain = load_agent()

logger.info("Agente RAG carregado com sucesso.")


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def get_chat_id(update: Update):
    """
    Retorna o identificador da conversa.
    """

    if not update.effective_chat:
        return None

    return update.effective_chat.id


def add_to_memory(
    chat_id: int,
    role: str,
    content: str,
):
    """
    Adiciona uma mensagem à memória da conversa.
    """

    conversation_memory[chat_id].append(
        {
            "role": role,
            "content": content,
        }
    )


def get_conversation_history(
    chat_id: int,
) -> str:
    """
    Converte o histórico da conversa para texto
    que será enviado ao RAG.
    """

    history = conversation_memory.get(
        chat_id,
        [],
    )

    if not history:
        return ""

    lines = []

    for message in history:

        role = message["role"]
        content = message["content"]

        if role == "user":
            prefix = "Paciente"

        else:
            prefix = "Assistente"

        lines.append(
            f"{prefix}: {content}"
        )

    return "\n".join(lines)


def clear_memory(chat_id: int):
    """
    Apaga o histórico da conversa.
    """

    conversation_memory.pop(
        chat_id,
        None,
    )


def split_message(
    text: str,
    max_length: int = MAX_TELEGRAM_MESSAGE_LENGTH,
):
    """
    Divide respostas muito grandes para respeitar
    o limite do Telegram.
    """

    if len(text) <= max_length:
        return [text]

    parts = []

    current = ""

    paragraphs = text.split("\n")

    for paragraph in paragraphs:

        candidate = (
            f"{current}\n{paragraph}"
            if current
            else paragraph
        )

        if len(candidate) <= max_length:

            current = candidate

        else:

            if current:
                parts.append(current)

            # Caso um único parágrafo seja maior que o limite
            while len(paragraph) > max_length:

                parts.append(
                    paragraph[:max_length]
                )

                paragraph = paragraph[
                    max_length:
                ]

            current = paragraph

    if current:
        parts.append(current)

    return parts


async def send_long_message(
    update: Update,
    text: str,
):
    """
    Envia uma resposta respeitando o limite
    de caracteres do Telegram.
    """

    parts = split_message(text)

    for part in parts:

        await update.message.reply_text(
            part
        )


# ============================================================
# /START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Inicia uma nova conversa.
    """

    chat_id = get_chat_id(update)

    if chat_id is not None:
        clear_memory(chat_id)

    greeting = get_greeting()

    mensagem = (
        f"{greeting}! 👋\n\n"
        "Eu sou o assistente virtual da "
        "Clínica Portela.\n\n"
        "Posso ajudar com informações sobre "
        "procedimentos, tratamentos, orientações, "
        "políticas de atendimento, agendamento e "
        "outras informações disponíveis na base da clínica.\n\n"
        "Como posso ajudar?"
    )

    await update.message.reply_text(
        mensagem
    )


# ============================================================
# /HELP
# ============================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Exibe exemplos de utilização.
    """

    mensagem = (
        "💬 *Como posso te ajudar?*\n\n"
        "Você pode perguntar, por exemplo:\n\n"
        "• Quais procedimentos a clínica oferece?\n"
        "• O que é preenchimento com ácido hialurônico?\n"
        "• O que são bioestimuladores?\n"
        "• Como funciona a limpeza de pele?\n"
        "• Quais são as contraindicações?\n"
        "• Como funciona o agendamento?\n"
        "• Qual é a política de cancelamento?\n"
        "• Quais formas de pagamento são aceitas?\n"
        "• Como funcionam as promoções?\n\n"
        "Também pode fazer perguntas em sequência. "
        "Eu consigo considerar o contexto recente da conversa."
    )

    await update.message.reply_text(
        mensagem,
        parse_mode="Markdown",
    )


# ============================================================
# /LIMPAR
# ============================================================

async def clear_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Limpa o contexto da conversa atual.
    """

    chat_id = get_chat_id(update)

    if chat_id is not None:
        clear_memory(chat_id)

    await update.message.reply_text(
        "🧹 Contexto da conversa limpo. "
        "Podemos começar novamente!"
    )


# ============================================================
# PROCESSAMENTO DAS MENSAGENS
# ============================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Processa mensagens enviadas pelo paciente.
    """

    if not update.message:
        return

    pergunta = update.message.text

    if not pergunta:
        return

    pergunta = pergunta.strip()

    if not pergunta:
        return

    chat_id = get_chat_id(update)

    if chat_id is None:
        return

    user = update.effective_user

    username = (
        user.username
        if user and user.username
        else "sem_username"
    )

    logger.info(
        "Mensagem recebida | chat_id=%s | usuario=%s | pergunta=%s",
        chat_id,
        username,
        pergunta,
    )

    # ========================================================
    # INDICADOR DE DIGITAÇÃO
    # ========================================================

    try:

        await context.bot.send_chat_action(
            chat_id=chat_id,
            action=ChatAction.TYPING,
        )

    except Exception:
        logger.exception(
            "Erro ao enviar indicador de digitação."
        )

    # ========================================================
    # HISTÓRICO
    # ========================================================

    history = get_conversation_history(
        chat_id
    )

    # ========================================================
    # PERGUNTA COM CONTEXTO
    # ========================================================

    if history:

        pergunta_para_rag = (
            "CONTEXTO DA CONVERSA RECENTE:\n"
            f"{history}\n\n"
            "NOVA MENSAGEM DO PACIENTE:\n"
            f"{pergunta}"
        )

    else:

        pergunta_para_rag = pergunta

    # ========================================================
    # SALVA MENSAGEM DO PACIENTE
    # ========================================================

    add_to_memory(
        chat_id,
        "user",
        pergunta,
    )

    # ========================================================
    # EXECUTA O RAG SEM BLOQUEAR O EVENT LOOP
    # ========================================================

    try:

        resposta = await asyncio.to_thread(
            answer_question,
            qa_chain,
            pergunta_para_rag,
        )

    except Exception:

        logger.exception(
            "Erro ao processar pergunta."
        )

        resposta = (
            "Desculpe, ocorreu um erro ao processar "
            "sua mensagem. Tente novamente em alguns instantes."
        )

    # ========================================================
    # SALVA RESPOSTA NA MEMÓRIA
    # ========================================================

    add_to_memory(
        chat_id,
        "assistant",
        resposta,
    )

    # ========================================================
    # LOG
    # ========================================================

    logger.info(
        "Resposta enviada | chat_id=%s | resposta=%s",
        chat_id,
        resposta,
    )

    # ========================================================
    # ENVIA RESPOSTA
    # ========================================================

    await send_long_message(
        update,
        resposta,
    )


# ============================================================
# TRATAMENTO DE ERROS
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Registra erros ocorridos no bot.
    """

    logger.error(
        "Erro não tratado no Telegram:",
        exc_info=context.error,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    token = os.getenv(
        "TELEGRAM_BOT_TOKEN"
    )

    if not token:

        raise ValueError(
            "TELEGRAM_BOT_TOKEN não encontrado "
            "no arquivo .env"
        )

    logger.info(
        "Iniciando bot da Clínica Portela..."
    )

    app = (
        ApplicationBuilder()
        .token(token)
        .build()
    )

    # --------------------------------------------------------
    # COMANDOS
    # --------------------------------------------------------

    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    app.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "limpar",
            clear_command,
        )
    )

    # --------------------------------------------------------
    # MENSAGENS
    # --------------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    # --------------------------------------------------------
    # ERROS
    # --------------------------------------------------------

    app.add_error_handler(
        error_handler
    )

    logger.info(
        "Bot da Clínica Portela iniciado com sucesso!"
    )

    logger.info(
        "Aguardando mensagens..."
    )

    app.run_polling()


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    main()
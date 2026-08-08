import os
import asyncio
import logging
from collections import defaultdict, deque

from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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
# Guarda as mensagens já no formato que rag_engine.answer_question
# espera em `historico`: [{"role": "user"/"assistant", "content": "..."}]

conversation_memory = defaultdict(
    lambda: deque(
        maxlen=MAX_HISTORY_MESSAGES
    )
)


# ============================================================
# CARREGAMENTO DO AGENTE
# ============================================================

logger.info("Carregando agente...")

agent = load_agent()

logger.info("Agente carregado com sucesso.")


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def get_chat_id(update: Update):
    if not update.effective_chat:
        return None
    return update.effective_chat.id


def add_to_memory(chat_id: int, role: str, content: str):
    conversation_memory[chat_id].append(
        {"role": role, "content": content}
    )


def get_conversation_history(chat_id: int) -> list:
    """Retorna o histórico já no formato de lista de mensagens
    esperado por rag_engine.answer_question(historico=...)."""
    return list(conversation_memory.get(chat_id, []))


def clear_memory(chat_id: int):
    conversation_memory.pop(chat_id, None)


def split_message(text: str, max_length: int = MAX_TELEGRAM_MESSAGE_LENGTH):
    if len(text) <= max_length:
        return [text]

    parts = []
    current = ""
    paragraphs = text.split("\n")

    for paragraph in paragraphs:
        candidate = f"{current}\n{paragraph}" if current else paragraph

        if len(candidate) <= max_length:
            current = candidate
        else:
            if current:
                parts.append(current)

            while len(paragraph) > max_length:
                parts.append(paragraph[:max_length])
                paragraph = paragraph[max_length:]

            current = paragraph

    if current:
        parts.append(current)

    return parts


async def send_long_message(update: Update, text: str):
    parts = split_message(text)
    for part in parts:
        await update.message.reply_text(part)


def menu_principal_keyboard() -> InlineKeyboardMarkup:
    """Menu inicial com os 4 atalhos. Cada botão só envia uma pergunta
    pronta pro agente processar normalmente (nenhuma lógica de
    agendamento duplicada aqui — quem decide o que fazer é o agente)."""
    botoes = [
        [InlineKeyboardButton("📅 Agendar consulta", callback_data="menu_agendar")],
        [InlineKeyboardButton("💰 Consultar valores", callback_data="menu_valores")],
        [InlineKeyboardButton("📋 Meus agendamentos", callback_data="menu_meus_agendamentos")],
        [InlineKeyboardButton("❓ Dúvidas sobre tratamentos", callback_data="menu_duvidas")],
    ]
    return InlineKeyboardMarkup(botoes)


# Texto que cada botão do menu "finge" que o paciente digitou
MENU_PROMPTS = {
    "menu_agendar": "Quero agendar uma consulta. Quais serviços vocês oferecem?",
    "menu_valores": "Quais são os serviços disponíveis e seus valores?",
    "menu_meus_agendamentos": "Quero ver meus agendamentos.",
    "menu_duvidas": "Tenho uma dúvida sobre um tratamento.",
}


# ============================================================
# PROCESSAMENTO CENTRAL (usado pelo texto livre E pelos botões)
# ============================================================

async def processar_pergunta(
    chat_id: int,
    pergunta: str,
    context: ContextTypes.DEFAULT_TYPE,
    reply_target,
):
    """
    Núcleo compartilhado: manda a pergunta pro agente, atualiza a
    memória e envia a resposta. `reply_target` é o objeto do
    telegram (update.message ou callback_query.message) que tem
    .reply_text().
    """

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    except Exception:
        logger.exception("Erro ao enviar indicador de digitação.")

    historico = get_conversation_history(chat_id)

    add_to_memory(chat_id, "user", pergunta)

    try:
        resposta = await asyncio.to_thread(
            answer_question,
            agent,
            pergunta,
            str(chat_id),   # telegram_chat_id — identifica o paciente pro booking_service
            historico,
        )
    except Exception:
        logger.exception("Erro ao processar pergunta.")
        resposta = (
            "Desculpe, ocorreu um erro ao processar sua mensagem. "
            "Tente novamente em alguns instantes."
        )

    add_to_memory(chat_id, "assistant", resposta)

    logger.info("Resposta enviada | chat_id=%s | resposta=%s", chat_id, resposta)

    for parte in split_message(resposta):
        await reply_target.reply_text(parte)


# ============================================================
# /START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = get_chat_id(update)

    if chat_id is not None:
        clear_memory(chat_id)

    greeting = get_greeting()

    mensagem = (
        f"{greeting}! 👋\n\n"
        "Eu sou o assistente virtual da Clínica Portela.\n\n"
        "Posso ajudar com informações sobre procedimentos, tratamentos, "
        "orientações, políticas de atendimento, agendamento e outras "
        "informações disponíveis na base da clínica.\n\n"
        "Como posso ajudar?"
    )

    await update.message.reply_text(mensagem, reply_markup=menu_principal_keyboard())


# ============================================================
# /HELP
# ============================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensagem = (
        "💬 *Como posso te ajudar?*\n\n"
        "Você pode perguntar, por exemplo:\n\n"
        "• Quais procedimentos a clínica oferece?\n"
        "• O que é preenchimento com ácido hialurônico?\n"
        "• Como funciona a limpeza de pele?\n"
        "• Quais são as contraindicações?\n"
        "• Tem horário disponível na sexta para X?\n"
        "• Quero agendar / cancelar / ver meus agendamentos\n"
        "• Qual é a política de cancelamento?\n\n"
        "Ou use o menu de botões enviado no /start."
    )
    await update.message.reply_text(mensagem, parse_mode="Markdown")


# ============================================================
# /LIMPAR
# ============================================================

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = get_chat_id(update)
    if chat_id is not None:
        clear_memory(chat_id)
    await update.message.reply_text("🧹 Contexto da conversa limpo. Podemos começar novamente!")


# ============================================================
# BOTÕES DO MENU PRINCIPAL
# ============================================================

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # remove o "relógio de carregando" do botão

    chat_id = get_chat_id(update)
    if chat_id is None:
        return

    pergunta = MENU_PROMPTS.get(query.data)
    if not pergunta:
        return

    user = update.effective_user
    username = user.username if user and user.username else "sem_username"
    logger.info(
        "Botão de menu | chat_id=%s | usuario=%s | botao=%s",
        chat_id, username, query.data,
    )

    await processar_pergunta(chat_id, pergunta, context, query.message)


# ============================================================
# PROCESSAMENTO DE TEXTO LIVRE
# ============================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    username = user.username if user and user.username else "sem_username"
    logger.info(
        "Mensagem recebida | chat_id=%s | usuario=%s | pergunta=%s",
        chat_id, username, pergunta,
    )

    await processar_pergunta(chat_id, pergunta, context, update.message)


# ============================================================
# TRATAMENTO DE ERROS
# ============================================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Erro não tratado no Telegram:", exc_info=context.error)


# ============================================================
# MAIN
# ============================================================

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN não encontrado no arquivo .env")

    logger.info("Iniciando bot da Clínica Portela...")

    app = ApplicationBuilder().token(token).build()

    # --------------------------------------------------------
    # COMANDOS
    # --------------------------------------------------------
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("limpar", clear_command))

    # --------------------------------------------------------
    # BOTÕES (callback_data começando com "menu_")
    # --------------------------------------------------------
    app.add_handler(CallbackQueryHandler(handle_menu_callback, pattern=r"^menu_"))

    # --------------------------------------------------------
    # MENSAGENS DE TEXTO LIVRE
    # --------------------------------------------------------
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # --------------------------------------------------------
    # ERROS
    # --------------------------------------------------------
    app.add_error_handler(error_handler)

    logger.info("Bot da Clínica Portela iniciado com sucesso!")
    logger.info("Aguardando mensagens...")

    app.run_polling()


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    main()
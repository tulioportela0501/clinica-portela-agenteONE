import os
import logging

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

from rag_engine import load_agent, answer_question

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# Carrega o agente RAG apenas uma vez
qa_chain = load_agent()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá! Eu sou o assistente virtual da Clínica Portela.\n\n"
        "Posso responder perguntas sobre:\n"
        "• Especialidades\n"
        "• Convênios\n"
        "• Horários\n"
        "• Valores\n"
        "• Políticas da clínica\n\n"
        "Como posso ajudar?"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Exemplos de perguntas:\n\n"
        "• Quais especialidades vocês atendem?\n"
        "• Vocês aceitam Unimed?\n"
        "• Qual o horário de funcionamento?\n"
        "• Quanto custa uma consulta?\n"
        "• Como cancelar uma consulta?"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    pergunta = update.message.text

    logger.info(f"Pergunta: {pergunta}")

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    resposta = answer_question(
        qa_chain,
        pergunta
    )

    await update.message.reply_text(resposta)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):

    logger.error("Erro:", exc_info=context.error)


def main():

    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN não encontrado no arquivo .env"
        )

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    app.add_error_handler(error_handler)

    logger.info("Bot iniciado com sucesso!")

    app.run_polling()


if __name__ == "__main__":
    main()
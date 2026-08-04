import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv
from rag_engine import load_agent, answer_question

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

qa_chain = load_agent()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! Sou o assistente virtual da Clínica Portela. 👋\n\n"
        "Pode me perguntar sobre especialidades, convênios, valores, "
        "horários de funcionamento e como agendar sua consulta."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Exemplos de perguntas que posso responder:\n"
        "• Quais especialidades vocês atendem?\n"
        "• Vocês aceitam o convênio Unimed?\n"
        "• Qual o horário de funcionamento?\n"
        "• Como faço para cancelar uma consulta?"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pergunta = update.message.text
    logger.info(f"Pergunta recebida: {pergunta}")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    resposta = answer_question(qa_chain, pergunta)
    await update.message.reply_text(resposta)

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN não encontrado no .env")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot rodando...")
    app.run_polling()

if __name__ == "__main__":
    main()
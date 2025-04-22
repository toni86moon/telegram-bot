import os
import asyncio
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# --- COSTANTI ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not BOT_TOKEN:
    raise ValueError("❌ Variabile d'ambiente BOT_TOKEN mancante.")
if not WEBHOOK_URL:
    raise ValueError("❌ Variabile d'ambiente WEBHOOK_URL mancante.")

# --- FLASK APP ---
app = Flask(__name__)
telegram_app = None  # Sarà inizializzato in main()

@app.route("/", methods=["GET"])
def home():
    return "🤖 Il bot è attivo."

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        update_data = request.get_json(force=True)
        if not update_data:
            logging.warning("⚠️ Nessun dato ricevuto nel body.")
            return "Bad Request", 400

        update = Update.de_json(update_data, telegram_app.bot)
        logging.info(f"📨 Update ricevuto: {update_data}")

        asyncio.run_coroutine_threadsafe(
            telegram_app.process_update(update),
            telegram_app.loop
        )

        return "OK", 200
    except Exception as e:
        logging.error(f"❌ Errore nel webhook: {e}")
        return "Internal Server Error", 500

# --- HANDLER ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! Sono attivo 🚀")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Comandi disponibili:\n/start\n/help")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Hai detto: {update.message.text}")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Comando non riconosciuto. Usa /help.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"❌ Errore gestito: {context.error}")
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Si è verificato un errore interno. Riprova più tardi."
            )
        except Exception as notify_error:
            logging.error(f"⚠️ Errore durante la notifica all'utente: {notify_error}")

# --- MAIN ASYNC FUNCTION ---
async def main():
    global telegram_app
    telegram_app = Application.builder().token(BOT_TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    telegram_app.add_handler(MessageHandler(filters.COMMAND, unknown))
    telegram_app.add_error_handler(error_handler)

    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    logging.info(f"✅ Webhook configurato su: {WEBHOOK_URL}/{BOT_TOKEN}")

    logging.info("🚀 Applicazione Telegram avviata in modalità webhook.")
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling()  # Necessario per gestire errori async anche in webhook mode
    await asyncio.Event().wait()

# --- AVVIO SERVER FLASK + LOOP ASYNC ---
if __name__ == "__main__":
    from threading import Thread

    # Avvio Flask in un thread separato
    flask_thread = Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": int(os.environ.get("PORT", 5000))})
    flask_thread.start()

    # Avvio asyncio loop principale
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("🛑 Interruzione manuale.")
    finally:
        if telegram_app:
            loop.run_until_complete(telegram_app.stop())
            loop.close()


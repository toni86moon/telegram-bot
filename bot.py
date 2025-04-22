import os
import asyncio
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# Configura il logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

# --- COSTANTI ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not BOT_TOKEN:
    raise ValueError("La variabile d'ambiente BOT_TOKEN non è configurata. Assicurati di fornire un token valido del bot.")

if not WEBHOOK_URL:
    raise ValueError("La variabile d'ambiente WEBHOOK_URL non è configurata. Assicurati di fornire un URL pubblico valido per il webhook.")

# --- FLASK SERVER ---
app = Flask(__name__)
telegram_app = None

@app.route("/", methods=["GET"])
def home():
    return "Il bot è attivo e in esecuzione."

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    if telegram_app:
        try:
            update_data = request.get_json(force=True)
            if not update_data:
                logging.warning("⚠️ Nessun dato ricevuto nell'aggiornamento.")
                return "Bad Request", 400

            logging.debug(f"📩 Dati aggiornamento ricevuti: {update_data}")
            update = Update.de_json(update_data, telegram_app.bot)
            logging.info(f"✅ Oggetto aggiornamento de-serializzato: {update.to_dict()}")

            from threading import Thread
            Thread(target=telegram_app.update_queue.put_nowait, args=(update,)).start()
        except Exception as e:
            logging.error(f"❌ Errore durante il webhook: {e}")
            return "Internal Server Error", 500
    return "OK", 200

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logging.info(f"📢 Comando /start ricevuto da: {update.effective_chat.id}")
        await update.message.reply_text("Ciao! Sono attivo e pronto ad aiutarti.")
    except Exception as e:
        logging.error(f"❌ Errore durante l'invio del messaggio /start: {e}")

async def main():
    global telegram_app
    telegram_app = Application.builder().token(BOT_TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start))

    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    logging.info(f"✅ Webhook configurato su: {WEBHOOK_URL}/{BOT_TOKEN}")

    try:
        logging.info("🚀 Bot in esecuzione...")
        await telegram_app.start()
        await asyncio.Event().wait()
    except Exception as e:
        logging.error(f"❌ Errore durante l'esecuzione del bot: {e}")
    finally:
        logging.info("🛑 Arresto del bot...")
        await telegram_app.stop()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    from threading import Thread
    flask_thread = Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": 5000})
    flask_thread.start()

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("🛑 Arresto del bot...")
    finally:
        loop.run_until_complete(telegram_app.stop())
        loop.close()

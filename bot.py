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
    logging.error("❌ La variabile d'ambiente BOT_TOKEN non è configurata.")
    raise ValueError("La variabile d'ambiente BOT_TOKEN non è configurata. Assicurati di fornire un token valido del bot.")

if not WEBHOOK_URL:
    logging.error("❌ La variabile d'ambiente WEBHOOK_URL non è configurata.")
    raise ValueError("La variabile d'ambiente WEBHOOK_URL non è configurata. Assicurati di fornire un URL pubblico valido per il webhook.")

logging.info(f"🔧 BOT_TOKEN: {'Configurato' if BOT_TOKEN else 'Non configurato'}")
logging.info(f"🔧 WEBHOOK_URL: {'Configurato' if WEBHOOK_URL else 'Non configurato'}")

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
    """Gestisce il comando /start."""
    try:
        logging.info(f"📢 Comando /start ricevuto da: {update.effective_chat.id}")
        await update.message.reply_text("Ciao! Sono attivo e pronto ad aiutarti.")
        logging.info("✅ Messaggio di risposta per /start inviato con successo.")
    except Exception as e:
        logging.error(f"❌ Errore durante l'invio del messaggio /start: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il comando /help."""
    try:
        logging.info(f"📢 Comando /help ricevuto da: {update.effective_chat.id}")
        await update.message.reply_text("Ecco i comandi disponibili:\n/start - Avvia il bot\n/help - Mostra questo messaggio")
        logging.info("✅ Messaggio di risposta per /help inviato con successo.")
    except Exception as e:
        logging.error(f"❌ Errore durante l'invio del messaggio /help: {e}")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Risponde ai messaggi di testo generici."""
    try:
        user_message = update.message.text.strip()
        logging.info(f"📩 Messaggio ricevuto: {user_message}")
        if not user_message:
            await update.message.reply_text("Non ho capito il tuo messaggio. Prova a scrivere qualcosa!")
        else:
            await update.message.reply_text(f"Hai detto: {user_message}")
        logging.info("✅ Messaggio di risposta inviato con successo.")
    except Exception as e:
        logging.error(f"❌ Errore durante l'invio della risposta: {e}")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Risponde ai comandi sconosciuti."""
    try:
        logging.info(f"❓ Comando sconosciuto ricevuto: {update.message.text}")
        await update.message.reply_text("Mi dispiace, non riconosco questo comando. Usa /help per vedere i comandi disponibili.")
        logging.info("✅ Messaggio di risposta per comando sconosciuto inviato con successo.")
    except Exception as e:
        logging.error(f"❌ Errore durante l'invio della risposta per comando sconosciuto: {e}")

# --- GESTIONE ERRORI ---
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log degli errori."""
    logging.error(f"❌ Errore globale: {context.error}")
    if update:
        logging.error(f"🔍 Contesto dell'aggiornamento: {update.to_dict()}")
    if update and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Si è verificato un errore interno. Riprova più tardi."
            )
        except Exception as e:
            logging.error(f"⚠️ Impossibile notificare l'utente dell'errore: {e}")

async def main():
    global telegram_app
    telegram_app = Application.builder().token(BOT_TOKEN).build()

    # Aggiungi handler
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    telegram_app.add_handler(MessageHandler(filters.COMMAND, unknown))  # Catch-all per comandi non riconosciuti

    # Aggiungi gestore degli errori
    telegram_app.add_error_handler(error_handler)

    # Configura il webhook
    response = await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    if response:
        logging.info(f"✅ Webhook configurato su: {WEBHOOK_URL}/{BOT_TOKEN}")
    else:
        logging.error(f"❌ Errore durante la configurazione del webhook su: {WEBHOOK_URL}/{BOT_TOKEN}")

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
    logging.info("✅ Server Flask avviato sulla porta 5000.")

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("🛑 Arresto del bot...")
    finally:
        loop.run_until_complete(telegram_app.stop())
        loop.close()

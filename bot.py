import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# --- COSTANTI ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # L'URL pubblico del tuo bot (es. https://<render-app>.onrender.com)

if not BOT_TOKEN or not WEBHOOK_URL:
    raise ValueError("Assicurati che BOT_TOKEN e WEBHOOK_URL siano configurati.")

# --- FLASK SERVER ---
app = Flask(__name__)
telegram_app = None  # Variabile globale per l'app Telegram

@app.route("/", methods=["GET"])
def home():
    return "Il bot è attivo e in esecuzione."

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    """Gestisce le richieste in arrivo da Telegram."""
    if telegram_app:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        print(f"✅ Aggiornamento ricevuto: {update.to_dict()}")  # Log dell'aggiornamento ricevuto
        telegram_app.update_queue.put_nowait(update)
    return "OK", 200

# --- FUNZIONI DEL BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il comando /start."""
    await update.message.reply_text("Ciao! Il bot è attivo con Webhook.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il comando /help."""
    await update.message.reply_text("Ecco cosa posso fare:\n/start - Avvia il bot\n/help - Mostra questo messaggio")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Risponde ai messaggi di testo."""
    await update.message.reply_text(f"Hai detto: {update.message.text}")

# --- GESTIONE ERRORI ---
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log degli errori."""
    print(f"❌ Errore: {context.error}")
    if update and update.effective_chat:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Si è verificato un errore.")

# --- CONFIGURAZIONE DEL BOT ---
async def main():
    global telegram_app
    telegram_app = Application.builder().token(BOT_TOKEN).build()

    # Aggiungi handler
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Aggiungi gestore degli errori
    telegram_app.add_error_handler(error_handler)

    # Configura il webhook
    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")

    print(f"✅ Webhook configurato su: {WEBHOOK_URL}/{BOT_TOKEN}")

    await telegram_app.start()
    await asyncio.Event().wait()

# --- AVVIO ---
if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    # Avvia il server Flask in un thread separato
    from threading import Thread
    flask_thread = Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": 5000})
    flask_thread.start()

    # Avvia il bot
    loop.run_until_complete(main())

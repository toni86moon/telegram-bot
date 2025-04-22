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
from supabase import create_client, Client
from difflib import get_close_matches  # Per suggerire comandi simili
from threading import Thread

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# --- COSTANTI ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

if not BOT_TOKEN:
    raise ValueError("❌ Variabile d'ambiente BOT_TOKEN mancante.")
if not WEBHOOK_URL:
    raise ValueError("❌ Variabile d'ambiente WEBHOOK_URL mancante.")
if not SUPABASE_URL or not SUPABASE_API_KEY:
    raise ValueError("❌ Variabili d'ambiente per Supabase mancanti.")
if not ADMIN_USER_ID:
    raise ValueError("❌ Variabile d'ambiente ADMIN_USER_ID mancante.")

# --- INIZIALIZZAZIONE SUPABASE ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)

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

        # Avvia la coroutine asincrona in un loop separato
        asyncio.run(handle_update(update))

        return "OK", 200
    except Exception as e:
        logging.error(f"❌ Errore nel webhook: {e}")
        return "Internal Server Error", 500

async def handle_update(update: Update):
    """Funzione asincrona per gestire gli aggiornamenti ricevuti."""
    try:
        await telegram_app.process_update(update)
    except Exception as e:
        logging.error(f"❌ Errore durante l'elaborazione dell'update: {e}")

# --- FUNZIONI DI SUPPORTO ---
def suggest_command(user_message):
    """Suggerisce un comando simile."""
    commands = ["/start", "/help", "/crea_missione"]
    suggestion = get_close_matches(user_message, commands, n=1)
    return suggestion[0] if suggestion else None

# --- HANDLER --- 

# Funzione per gestire la registrazione dell'utente
async def register_user(telegram_id, username_instagram):
    try:
        result = supabase.table('utenti').select('telegram_id').eq('telegram_id', telegram_id).execute()
        if len(result.data) == 0:
            supabase.table('utenti').insert({
                'telegram_id': telegram_id,
                'username_instagram': username_instagram,
            }).execute()
            logging.info(f"👤 Utente {telegram_id} registrato.")
        else:
            logging.info(f"👤 Utente {telegram_id} già esistente.")
    except Exception as e:
        logging.error(f"❌ Errore durante la registrazione dell'utente {telegram_id}: {e}")

# Funzione per creare una missione
async def create_mission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id == int(ADMIN_USER_ID):  # Controlla se è l'amministratore
        try:
            args = update.message.text.split(maxsplit=2)[1:]  # Ignora il comando stesso
            if len(args) < 2:
                await update.message.reply_text("⚠️ Sintassi non corretta! Usa /crea_missione <tipo> <url>\nEsempio: /crea_missione follow https://instagram.com/example")
                return

            mission_type, mission_url = args
            supabase.table('missioni').insert({
                'tipo': mission_type,
                'url': mission_url
            }).execute()
            await update.message.reply_text(f"✅ Missione '{mission_type}' creata con successo!")
        except Exception as e:
            logging.error(f"❌ Errore durante la creazione della missione: {e}")
            await update.message.reply_text("❌ Si è verificato un errore durante la creazione della missione.")
    else:
        await update.message.reply_text("🚫 Non sei autorizzato a creare missioni.")

# Funzione per tracciare l'attività
async def log_activity(telegram_id, evento, descrizione):
    try:
        supabase.table('log_attivita').insert({
            'telegram_id': telegram_id,
            'evento': evento,
            'descrizione': descrizione
        }).execute()
    except Exception as e:
        logging.error(f"❌ Errore durante il log dell'attività: {e}")

# --- HANDLER PRINCIPALI ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.message.from_user.id
    username_instagram = update.message.from_user.username  # Sostituire con il vero username Instagram se necessario
    await register_user(telegram_id, username_instagram)
    await update.message.reply_text("Ciao! Sono attivo 🚀")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Comandi disponibili:\n/start\n/help\n/crea_missione")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    if user_message.startswith("/"):
        suggestion = suggest_command(user_message)
        if suggestion:
            await update.message.reply_text(
                f"❓ Comando '{user_message}' non riconosciuto. Intendevi '{suggestion}'? Usa /help per vedere i comandi disponibili."
            )
        else:
            await update.message.reply_text(
                f"❓ Comando '{user_message}' non riconosciuto. Usa /help per vedere i comandi disponibili."
            )
    else:
        await update.message.reply_text("Non ho capito. Usa /help per vedere cosa posso fare.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    await update.message.reply_text(f"Hai detto: {user_message}. Usa /help per vedere i comandi disponibili.")

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
    telegram_app.add_handler(CommandHandler("crea_missione", create_mission))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    telegram_app.add_handler(MessageHandler(filters.COMMAND, unknown))
    telegram_app.add_error_handler(error_handler)

    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    logging.info(f"✅ Webhook configurato su: {WEBHOOK_URL}/{BOT_TOKEN}")

    logging.info("🚀 Applicazione Telegram avviata in modalità webhook.")
    await telegram_app.initialize()
    await telegram_app.start()
    await asyncio.Event().wait()

# --- AVVIO SERVER FLASK + LOOP ASYNC ---
if __name__ == "__main__":
    # Avvio Flask in un thread separato
    flask_port = int(os.environ.get("PORT", 5000))
    logging.info(f"✅ Server Flask avviato sulla porta {flask_port}.")
    flask_thread = Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": flask_port})
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





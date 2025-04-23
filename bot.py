import os
import asyncio
import logging
from flask import Flask, request
from telegram import Update, ChatMember
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

# --- VARIABILI GLOBALI ---
missioni = {}  # Dict con {chat_id: {user_id: missione}}
missioni_attive = {}  # Dict con {chat_id: testo_missione}

# --- FLASK APP ---
app = Flask(__name__)
telegram_app = None

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

# --- UTILS ---
async def is_admin(chat_id, user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except Exception as e:
        logging.error(f"Errore controllo admin: {e}")
        return False

# --- HANDLER ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! Sono attivo 🚀")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Comandi disponibili:\n/start\n/help\n/crea_missione <testo>\n/missione\n/verifica")

async def crea_missione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not await is_admin(chat_id, user_id, context):
        await update.message.reply_text("❌ Solo gli admin possono creare missioni.")
        return

    testo = " ".join(context.args)
    if not testo:
        await update.message.reply_text("ℹ️ Usa: /crea_missione <testo della missione>")
        return

    missioni_attive[chat_id] = testo
    await update.message.reply_text(f"✅ Missione creata:\n{testo}")

async def missione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    testo = missioni_attive.get(chat_id)

    if not testo:
        await update.message.reply_text("❌ Nessuna missione disponibile.")
        return

    missioni.setdefault(chat_id, {})[user_id] = testo
    await update.message.reply_text(f"🌟 Ecco la tua missione:\n{testo}\nScrivi /verifica quando hai finito.")

async def verifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    missione_utente = missioni.get(chat_id, {}).get(user_id)

    if not missione_utente:
        await update.message.reply_text("ℹ️ Non hai alcuna missione attiva. Usa /missione.")
        return

    # Placeholder per controllo Instaloader
    # TODO: Integrazione con Instaloader e verifica missione

    # Placeholder per codice sconto
    codice_sconto = "SCONTO10"
    await update.message.reply_text(f"🎉 Missione completata! Il tuo codice sconto è: {codice_sconto}")
    missioni[chat_id].pop(user_id, None)

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

# --- PLACEHOLDER ECHO HANDLER ---
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(update.message.text)

# --- MAIN ASYNC FUNCTION ---
async def main():
    global telegram_app
    telegram_app = Application.builder().token(BOT_TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(CommandHandler("crea_missione", crea_missione))
    telegram_app.add_handler(CommandHandler("missione", missione))
    telegram_app.add_handler(CommandHandler("verifica", verifica))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
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
    from threading import Thread

    flask_thread = Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": int(os.environ.get("PORT", 5000))})
    flask_thread.start()

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






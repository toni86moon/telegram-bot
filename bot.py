import os
import requests
import asyncio
from flask import Flask
import threading
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters
)
from telegram.error import Conflict

# --- COSTANTI ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
TUO_TELEGRAM_ID_ADMIN = int(os.getenv("TUO_TELEGRAM_ID_ADMIN", "0"))

if not all([BOT_TOKEN, SUPABASE_URL, SUPABASE_API_KEY]):
    raise ValueError("Errore: Assicurati che BOT_TOKEN, SUPABASE_URL e SUPABASE_API_KEY siano configurati.")

# --- FUNZIONI API SUPABASE ---
async def add_utente(telegram_id):
    """Aggiunge un utente alla tabella 'utenti' su Supabase."""
    try:
        headers = {
            "apikey": SUPABASE_API_KEY,
            "Authorization": f"Bearer {SUPABASE_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "telegram_id": telegram_id,
        }
        response = requests.post(f"{SUPABASE_URL}/rest/v1/utenti", headers=headers, json=data)
        response.raise_for_status()
        print(f"✅ Utente {telegram_id} aggiunto alla tabella utenti.")
    except Exception as e:
        print(f"❌ Errore durante l'aggiunta dell'utente: {e}")
        raise

async def get_missioni():
    """Recupera le missioni attive dalla tabella 'missioni' su Supabase."""
    try:
        headers = {
            "apikey": SUPABASE_API_KEY,
            "Authorization": f"Bearer {SUPABASE_API_KEY}",
        }
        response = requests.get(f"{SUPABASE_URL}/rest/v1/missioni?attiva=eq.true", headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Errore durante il recupero delle missioni: {e}")
        raise

async def create_missione(tipo, url):
    """Crea una nuova missione nella tabella 'missioni' su Supabase."""
    try:
        headers = {
            "apikey": SUPABASE_API_KEY,
            "Authorization": f"Bearer {SUPABASE_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "tipo": tipo,
            "url": url,
            "attiva": True,
        }
        response = requests.post(f"{SUPABASE_URL}/rest/v1/missioni", headers=headers, json=data)
        response.raise_for_status()
        print(f"✅ Missione creata: Tipo={tipo}, URL={url}")
    except Exception as e:
        print(f"❌ Errore durante la creazione della missione: {e}")
        raise

# --- FUNZIONI DEL BOT ---
async def log_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log degli aggiornamenti ricevuti dal bot, utile per diagnosticare problemi."""
    print(f"Aggiornamento ricevuto: {update}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il comando /start."""
    user_id = update.effective_user.id
    try:
        await add_utente(user_id)
        await update.message.reply_text("Benvenuto! Usa /missioni per vedere le missioni disponibili.")
    except Exception:
        await update.message.reply_text("❌ Errore durante l'aggiunta dell'utente al database.")

async def missioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il comando /missioni."""
    try:
        rows = await get_missioni()
        if not rows:
            await update.message.reply_text("Al momento non ci sono missioni attive.")
            return

        messaggio = "🎯 Missioni disponibili:\n"
        for row in rows:
            messaggio += f"\n🆔 ID: {row['id']}\n📌 Tipo: {row['tipo']}\n🔗 URL: {row['url']}\n"
        await update.message.reply_text(messaggio)
    except Exception:
        await update.message.reply_text("❌ Errore durante il recupero delle missioni.")

async def crea_missione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il comando /crea_missione."""
    if update.effective_user.id != TUO_TELEGRAM_ID_ADMIN:
        await update.message.reply_text("⚠️ Solo l'amministratore può creare nuove missioni.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Formato non valido. Usa: /crea_missione <tipo> <url>\n"
            "Esempio: /crea_missione Like https://instagram.com/post"
        )
        return

    tipo, url = context.args[0], context.args[1]
    try:
        await create_missione(tipo, url)
        await update.message.reply_text(f"✅ Missione creata con successo!\n📌 Tipo: {tipo}\n🔗 URL: {url}")
    except Exception:
        await update.message.reply_text("❌ Errore durante la creazione della missione.")

# --- AVVIO BOT ---
async def main():
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        await app.bot.delete_webhook(drop_pending_updates=True)

        # Aggiungi handler
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("missioni", missioni))
        app.add_handler(CommandHandler("crea_missione", crea_missione))
        app.add_handler(MessageHandler(filters.ALL, log_update))  # Per loggare tutti gli aggiornamenti

        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()

    except Conflict as e:
        print(f"Errore: {e}")
    except Exception as e:
        print(f"Errore generale: {e}")

# --- SERVER FLASK ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Il bot è attivo e in esecuzione."

def run_flask():
    app.run(host='0.0.0.0', port=5000)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    asyncio.run(main())



import asyncio
import sqlite3
import requests
import random
import string
import instaloader
import os
from flask import Flask
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler,
    filters
)
from telegram.error import Conflict

# --- COSTANTI ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
WOOCOMMERCE_API_URL = os.getenv("WOOCOMMERCE_API_URL")
WOOCOMMERCE_KEY = os.getenv("WOOCOMMERCE_KEY")
WOOCOMMERCE_SECRET = os.getenv("WOOCOMMERCE_SECRET")
TUO_TELEGRAM_ID_ADMIN = int(os.getenv("TUO_TELEGRAM_ID_ADMIN", "0"))
CANAL_TELEGRAM_ID = os.getenv("CANAL_TELEGRAM_ID")

if not all([BOT_TOKEN, WOOCOMMERCE_API_URL, WOOCOMMERCE_KEY, WOOCOMMERCE_SECRET, CANAL_TELEGRAM_ID]):
    raise ValueError("Errore: Assicurati che tutte le variabili d'ambiente siano configurate.")

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect("utenti.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS utenti (
        telegram_id INTEGER PRIMARY KEY,
        username_instagram TEXT,
        punti INTEGER DEFAULT 0
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS missioni (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT,
        url TEXT,
        attiva INTEGER DEFAULT 1
    )
    """)
    conn.commit()
    return conn, cursor

conn, cursor = init_db()

# --- FUNZIONI ---
def genera_codice_sconto(percentuale: int = 10) -> str:
    codice = "ENGAGE" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    dati = {
        "code": codice,
        "discount_type": "percent",
        "amount": str(percentuale),
        "individual_use": True,
        "usage_limit": 1,
        "usage_limit_per_user": 1
    }
    try:
        r = requests.post(
            WOOCOMMERCE_API_URL + "coupons",
            auth=(WOOCOMMERCE_KEY, WOOCOMMERCE_SECRET),
            json=dati
        )
        r.raise_for_status()
        return codice
    except requests.exceptions.RequestException as e:
        print(f"Errore durante la richiesta API WooCommerce: {e}")
        return None

async def verifica_iscrizione_canale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        chat_member = await context.bot.get_chat_member(chat_id=CANAL_TELEGRAM_ID, user_id=user_id)
        return chat_member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Errore durante la verifica dell'iscrizione al canale: {e}")
        return False

# --- COMANDI BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("INSERT OR IGNORE INTO utenti (telegram_id) VALUES (?)", (user_id,))
    conn.commit()
    await update.message.reply_text("Benvenuto! Usa /missioni per vedere le missioni disponibili oppure aggiorna il tuo profilo con /instagram.")

async def missioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_iscritto = await verifica_iscrizione_canale(update, context)
    if not is_iscritto:
        await update.message.reply_text("Devi iscriverti al canale per accedere alle missioni!")
        return
    
    cursor.execute("SELECT id, tipo, url FROM missioni WHERE attiva = 1")
    missioni_attive = cursor.fetchall()
    if not missioni_attive:
        await update.message.reply_text("Al momento non ci sono missioni attive.")
        return

    messaggio = "🎯 Missioni disponibili:\n"
    for mid, tipo, url in missioni_attive:
        messaggio += f"\n🆔 ID: {mid}\n📌 Tipo: {tipo}\n🔗 URL: {url}\n"
    await update.message.reply_text(messaggio)

async def crea_missione(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        cursor.execute(
            "INSERT INTO missioni (tipo, url, attiva) VALUES (?, ?, 1)",
            (tipo, url)
        )
        conn.commit()
        await update.message.reply_text(f"✅ Missione creata con successo!\n📌 Tipo: {tipo}\n🔗 URL: {url}")
    except Exception as e:
        print(f"Errore durante la creazione della missione: {e}")
        await update.message.reply_text("❌ Errore durante la creazione della missione.")

async def elimina_missione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != TUO_TELEGRAM_ID_ADMIN:
        await update.message.reply_text("⚠️ Solo l'amministratore può eliminare missioni.")
        return

    if len(context.args) < 1:
        await update.message.reply_text("⚠️ Usa: /elimina_missione <ID>")
        return

    missione_id = context.args[0]
    try:
        cursor.execute("DELETE FROM missioni WHERE id = ?", (missione_id,))
        conn.commit()
        await update.message.reply_text(f"✅ Missione {missione_id} eliminata con successo.")
    except Exception as e:
        print(f"Errore durante l'eliminazione della missione: {e}")
        await update.message.reply_text("❌ Errore durante l'eliminazione della missione.")

# --- AVVIO BOT ---
async def main():
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        await app.bot.delete_webhook(drop_pending_updates=True)

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("missioni", missioni))
        app.add_handler(CommandHandler("crea_missione", crea_missione))
        app.add_handler(CommandHandler("elimina_missione", elimina_missione))

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





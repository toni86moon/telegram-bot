import asyncio
import asyncpg
import os
import requests
import random
import string
from flask import Flask
import threading
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters
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
async def init_db():
    try:
        conn = await asyncpg.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            port=os.getenv("DB_PORT")
        )
        print("✅ Connessione al database riuscita!")
        
        # Crea le tabelle se non esistono
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS utenti (
            telegram_id BIGINT PRIMARY KEY,
            username_instagram VARCHAR(255),
            punti INT DEFAULT 0
        )
        """)
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS missioni (
            id SERIAL PRIMARY KEY,
            tipo VARCHAR(255),
            url TEXT,
            attiva BOOLEAN DEFAULT TRUE
        )
        """)
        return conn

    except Exception as e:
        print(f"❌ Errore di connessione al database: {e}")
        raise

db_conn = None  # Variabile globale per la connessione al database

# --- FUNZIONI ---
async def log_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log degli aggiornamenti ricevuti dal bot, utile per diagnosticare problemi."""
    print(f"Aggiornamento ricevuto: {update}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        await db_conn.execute(
            "INSERT INTO utenti (telegram_id) VALUES ($1) ON CONFLICT DO NOTHING",
            user_id
        )
        print(f"✅ Utente {user_id} aggiunto al database.")
        await update.message.reply_text("Benvenuto! Usa /missioni per vedere le missioni disponibili.")
    except Exception as e:
        print(f"❌ Errore durante l'aggiunta dell'utente: {e}")
        await update.message.reply_text("❌ Errore durante l'aggiunta dell'utente al database.")

async def missioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rows = await db_conn.fetch("SELECT id, tipo, url FROM missioni WHERE attiva = TRUE")
        if not rows:
            await update.message.reply_text("Al momento non ci sono missioni attive.")
            return

        messaggio = "🎯 Missioni disponibili:\n"
        for row in rows:
            messaggio += f"\n🆔 ID: {row['id']}\n📌 Tipo: {row['tipo']}\n🔗 URL: {row['url']}\n"
        await update.message.reply_text(messaggio)
    except Exception as e:
        print(f"❌ Errore durante il recupero delle missioni: {e}")
        await update.message.reply_text("❌ Errore durante il recupero delle missioni.")

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
        query = "INSERT INTO missioni (tipo, url, attiva) VALUES ($1, $2, $3)"
        await db_conn.execute(query, tipo, url, True)
        print(f"✅ Missione creata: Tipo={tipo}, URL={url}")
        await update.message.reply_text(f"✅ Missione creata con successo!\n📌 Tipo: {tipo}\n🔗 URL: {url}")
    except Exception as e:
        print(f"❌ Errore durante la creazione della missione: {e}")
        await update.message.reply_text("❌ Errore durante la creazione della missione.")

# --- AVVIO BOT ---
async def main():
    global db_conn
    try:
        db_conn = await init_db()

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
    finally:
        if db_conn:
            await db_conn.close()
            print("✅ Connessione al database chiusa.")

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




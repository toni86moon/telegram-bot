import asyncio
import mysql.connector
from mysql.connector import Error
import requests
import random
import string
import os
from flask import Flask
import threading
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes
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
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        cursor = conn.cursor()
        
        # Crea le tabelle se non esistono
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS utenti (
            telegram_id BIGINT PRIMARY KEY,
            username_instagram VARCHAR(255),
            punti INT DEFAULT 0
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS missioni (
            id INT AUTO_INCREMENT PRIMARY KEY,
            tipo VARCHAR(255),
            url TEXT,
            attiva TINYINT DEFAULT 1
        )
        """)
        
        conn.commit()
        return conn, cursor

    except Error as e:
        print(f"Errore di connessione al database: {e}")
        raise

conn, cursor = init_db()

# --- FUNZIONI ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute(
        "INSERT IGNORE INTO utenti (telegram_id) VALUES (%s)",
        (user_id,)
    )
    conn.commit()
    await update.message.reply_text("Benvenuto! Usa /missioni per vedere le missioni disponibili.")

async def missioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text("⚠️ Formato non valido. Usa: /crea_missione <tipo> <url>")
        return

    tipo, url = context.args[0], context.args[1]
    cursor.execute(
        "INSERT INTO missioni (tipo, url, attiva) VALUES (%s, %s, %s)",
        (tipo, url, True)
    )
    conn.commit()
    await update.message.reply_text(f"✅ Missione creata con successo!\n📌 Tipo: {tipo}\n🔗 URL: {url}")

# --- AVVIO BOT ---
async def main():
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        await app.bot.delete_webhook(drop_pending_updates=True)

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("missioni", missioni))
        app.add_handler(CommandHandler("crea_missione", crea_missione))

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





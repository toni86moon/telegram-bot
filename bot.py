import asyncio  # ✅ IMPORTATO QUI IN ALTO
import sqlite3
import requests
import random
import string
import instaloader
import os  # Nuovo per le variabili d'ambiente
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler,
    filters, ConversationHandler
)

# --- COSTANTI ---
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Variabile d'ambiente per il token del bot
WOOCOMMERCE_API_URL = os.getenv("WOOCOMMERCE_API_URL")  # URL WooCommerce dal file .env
WOOCOMMERCE_KEY = os.getenv("WOOCOMMERCE_KEY")  # Chiave WooCommerce
WOOCOMMERCE_SECRET = os.getenv("WOOCOMMERCE_SECRET")  # Segreto WooCommerce
TUO_TELEGRAM_ID_ADMIN = int(os.getenv("TUO_TELEGRAM_ID_ADMIN", "0"))  # ID admin Telegram
CANAL_TELEGRAM_ID = os.getenv("CANAL_TELEGRAM_ID")  # ID del canale Telegram

# Verifica che le variabili essenziali siano state caricate
if not all([BOT_TOKEN, WOOCOMMERCE_API_URL, WOOCOMMERCE_KEY, WOOCOMMERCE_SECRET, CANAL_TELEGRAM_ID]):
    raise ValueError("Errore: Assicurati che tutte le variabili d'ambiente essenziali siano configurate (BOT_TOKEN, WOOCOMMERCE_API_URL, ecc.).")

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

# --- NUOVA FUNZIONE: Verifica iscrizione al canale ---
async def verifica_iscrizione_canale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        user_id = update.effective_user.id
        member = await context.bot.get_chat_member(CANAL_TELEGRAM_ID, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        else:
            await update.message.reply_text(f"Per partecipare alle missioni, devi essere iscritto al nostro canale Telegram: {CANAL_TELEGRAM_ID}")
            return False
    except Exception as e:
        await update.message.reply_text(f"Errore durante il controllo dell'iscrizione al canale: {str(e)}")
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

# --- AVVIO BOT ---
async def main():
    # Crea l'applicazione Telegram
    app = Application.builder().token(BOT_TOKEN).build()

    # Aggiungi handler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("missioni", missioni))

    # Avvia il bot in modalità polling
    await app.run_polling()

# --- BLOCCO DI AVVIO ---
if __name__ == "__main__":
    asyncio.run(main())  # Non chiude il ciclo di eventi automaticamente






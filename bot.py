import asyncio
import sqlite3
import requests
import random
import string
import instaloader
import os  # Nuovo per le variabili d'ambiente
from flask import Flask
import threading
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler,
    filters, ConversationHandler
)
from telegram.error import Conflict  # Importato per gestire errori di conflitto

# --- COSTANTI ---
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Variabile d'ambiente per il token del bot
WOOCOMMERCE_API_URL = os.getenv("WOOCOMMERCE_API_URL")  # URL WooCommerce
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

# --- NUOVO COMANDO: Creazione di Missioni ---
async def crea_missione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Verifica che solo l'amministratore possa creare missioni
    if update.effective_user.id != TUO_TELEGRAM_ID_ADMIN:
        await update.message.reply_text("⚠️ Solo l'amministratore può creare nuove missioni.")
        return

    # Controlla che siano stati forniti i parametri necessari
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Formato non valido. Usa: /crea_missione <tipo> <url>\n"
            "Esempio: /crea_missione Like https://instagram.com/post"
        )
        return

    # Recupera i parametri dal comando
    tipo = context.args[0]
    url = context.args[1]

    # Inserisce la missione nel database
    cursor.execute(
        "INSERT INTO missioni (tipo, url, attiva) VALUES (?, ?, 1)",
        (tipo, url)
    )
    conn.commit()

    # Conferma all'amministratore che la missione è stata creata
    await update.message.reply_text(f"✅ Missione creata con successo!\n📌 Tipo: {tipo}\n🔗 URL: {url}")

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
    try:
        # Crea l'applicazione Telegram
        app = Application.builder().token(BOT_TOKEN).build()

        # Elimina eventuali webhook esistenti
        await app.bot.delete_webhook(drop_pending_updates=True)

        # Aggiungi handler
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("missioni", missioni))
        app.add_handler(CommandHandler("crea_missione", crea_missione))

        # Avvia il bot in modalità polling
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        # Mantieni il bot attivo
        await asyncio.Event().wait()

    except Conflict as e:
        # Gestione dell'errore di conflitto
        print("Errore: un'altra istanza del bot è già in esecuzione.")
        print(f"Dettagli dell'errore: {e}")

    except Exception as e:
        # Gestione di errori generici
        print("Si è verificato un errore imprevisto.")
        print(f"Dettagli dell'errore: {e}")

# --- SERVER FLASK ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Il bot è attivo e in esecuzione."

def run_flask():
    app.run(host='0.0.0.0', port=5000)  # Porta richiesta da Render

# --- BLOCCO DI AVVIO ---
if __name__ == "__main__":
    # Avvia Flask in un thread separato
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    try:
        asyncio.run(main())  # Usa asyncio.run solo quando l'event loop non è già in esecuzione
    except RuntimeError as e:
        print("Errore nel ciclo di eventi: forse il loop è già in esecuzione.")
        print(f"Dettagli dell'errore: {e}")





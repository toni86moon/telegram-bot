import asyncio  # ✅ IMPORTATO QUI IN ALTO
import sqlite3
import requests
import random
import string
import instaloader
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler,
    filters, ConversationHandler
)

# --- COSTANTI ---
BOT_TOKEN = "7680191017:AAHZEmD-74BIlK44JYa5O_2K3h0XVaEZZJE"
WOOCOMMERCE_API_URL = "https://example.com/wp-json/wc/v3/"
WOOCOMMERCE_KEY = "ck_0b35ae594925fa35435485fdaa84282698241855"
WOOCOMMERCE_SECRET = "cs_3fc4a9e9deed68036a1f5f2f06046a73a75fd2ce"
TUO_TELEGRAM_ID_ADMIN = "Udispay"
INSERISCI_USERNAME_IG = "mordiamo"
CANAL_TELEGRAM_ID = "@ornoirsmart"

# --- DATABASE ---
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

def verifica_interazione(username: str, url: str, tipo: str) -> bool:
    L = instaloader.Instaloader()
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        for post in profile.get_posts():
            if url in post.url:
                return True
    except Exception as e:
        print(f"Errore verifica IG per {username}: {e}")
    return False

# --- NUOVA FUNZIONE: Verifica iscrizione al canale ---
async def verifica_iscrizione_canale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(CANAL_TELEGRAM_ID, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        else:
            await update.message.reply_text(f"Per partecipare alle missioni, devi essere iscritto al nostro canale Telegram: {CANAL_TELEGRAM_ID}")
            return False
    except Exception as e:
        print(f"Errore durante il controllo dell'iscrizione al canale: {e}")
        await update.message.reply_text(f"Non riesco a verificare la tua iscrizione al canale. Assicurati di essere membro di {CANAL_TELEGRAM_ID}.")
        return False

# --- COMANDI BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("INSERT OR IGNORE INTO utenti (telegram_id) VALUES (?)", (user_id,))
    conn.commit()
    await update.message.reply_text("Benvenuto! Usa /missioni per vedere le missioni disponibili oppure aggiorna il tuo profilo con /instagram.")

async def aggiorna_ig(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Inserisci il tuo username Instagram:")
    return INSERISCI_USERNAME_IG

async def inserisci_username_ig(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip().lstrip("@").lower()
    user_id = update.effective_user.id
    cursor.execute("UPDATE utenti SET username_instagram = ? WHERE telegram_id = ?", (username, user_id))
    conn.commit()
    await update.message.reply_text(f"Username Instagram aggiornato con successo: {username}")
    return ConversationHandler.END

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

async def profilo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT username_instagram, punti FROM utenti WHERE telegram_id = ?", (user_id,))
    utente = cursor.fetchone()
    if not utente:
        await update.message.reply_text("Profilo non trovato.")
        return
    username, punti = utente
    await update.message.reply_text(f"👤 Username IG: {username or 'Non impostato'}\n⭐️ Punti: {punti}")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != TUO_TELEGRAM_ID_ADMIN:
        await update.message.reply_text("Accesso negato.")
        return
    cursor.execute("SELECT id, tipo, url, attiva FROM missioni")
    missioni = cursor.fetchall()
    messaggio = "📊 Pannello Admin - Missioni:\n"
    for mid, tipo, url, attiva in missioni:
        stato = "✅ Attiva" if attiva else "⛔ Disattivata"
        messaggio += f"\nID: {mid}\nTipo: {tipo}\nURL: {url}\nStato: {stato}\n"
    await update.message.reply_text(messaggio)
    if context.args and context.args[0] == "notifica":
        await notifica_nuova_missione(context.bot, "🚀 È stata lanciata una nuova missione! Usa /missioni per scoprirla!")

# --- AVVIO BOT ---
async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("instagram", aggiorna_ig)],
        states={INSERISCI_USERNAME_IG: [MessageHandler(filters.TEXT & ~filters.COMMAND, inserisci_username_ig)]},
        fallbacks=[]
    )
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("missioni", missioni))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("profilo", profilo))
    await app.run_polling()

# --- BLOCCO DI AVVIO ---
if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(main())
        else:
            loop.run_until_complete(main())
    except RuntimeError as e:
        print(f"Errore nel ciclo di eventi: {e}")





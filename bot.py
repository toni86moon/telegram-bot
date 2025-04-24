import os
import logging
import instaloader
import requests
from urllib.parse import urlparse
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from supabase import create_client

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Env Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("TUO_TELEGRAM_ID_ADMIN"))
CANAL_TELEGRAM_ID = os.getenv("CANAL_TELEGRAM_ID")
WOOCOMMERCE_URL = os.getenv("WOOCOMMERCE_API_URL")
WOOCOMMERCE_KEY = os.getenv("WOOCOMMERCE_KEY")
WOOCOMMERCE_SECRET = os.getenv("WOOCOMMERCE_SECRET")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # URL pubblico del webhook
PORT = int(os.getenv("PORT", 8443))  # Porta su cui l'applicazione ascolta
VERIFICA_TRAMITE_API = False  # Se impostato su True, salta il controllo con Instaloader

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_API_KEY)

# Instaloader setup
L = instaloader.Instaloader()

# Menu
MAIN_MENU = ReplyKeyboardMarkup([
    ["/missione", "/verifica"],
    ["/punti", "/getlink", "/help"]
], resize_keyboard=True)

# Funzione di verifica missione
def verifica_missione_completata(tipo, username, post):
    if tipo == "like":
        return username in [like.username for like in post.get_likes()]
    elif tipo == "follow":
        return username in [f.username for f in post.owner_profile.get_followers()]
    elif tipo == "comment":
        return username in [c.owner.username for c in post.get_comments()]
    return False

# Comandi del bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = supabase.table("utenti").select("*").eq("telegram_id", telegram_id).execute()
    if not user.data:
        supabase.table("utenti").insert({"telegram_id": telegram_id, "punti": 0}).execute()
        await update.message.reply_text("👋 Benvenuto nel bot missioni! Usa /insta <username> per collegare Instagram.", reply_markup=MAIN_MENU)
    else:
        await update.message.reply_text("Bentornato! 🎉", reply_markup=MAIN_MENU)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Comandi:\n/start - Registrazione\n/insta <username> - Collega Instagram\n/missione [tipo] - Ricevi una missione (like, comment, follow)\n/verifica - Verifica completamento\n/punti - Punti attuali\n/getlink - Ottieni il tuo link referral", reply_markup=MAIN_MENU)

async def insta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if len(context.args) != 1:
        await update.message.reply_text("❌ Usa /insta tuo_username", reply_markup=MAIN_MENU)
        return
    supabase.table("utenti").update({"username_instagram": context.args[0]}).eq("telegram_id", telegram_id).execute()
    await update.message.reply_text(f"✅ Username Instagram impostato: {context.args[0]}", reply_markup=MAIN_MENU)

async def missione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=CANAL_TELEGRAM_ID, user_id=telegram_id)
        if member.status not in ["member", "administrator", "creator"]:
            await update.message.reply_text("🔒 Per ricevere missioni devi iscriverti al canale prima.")
            return
    except Exception as e:
        logging.error(f"Errore nel controllo iscrizione canale: {e}")
        await update.message.reply_text("⚠️ Non riesco a verificare se sei iscritto al canale. Riprova più tardi.")
        return

    filtro = {}
    if context.args:
        tipo = context.args[0].lower()
        if tipo not in ["like", "comment", "follow"]:
            await update.message.reply_text("❌ Tipo non valido. Usa: /missione like, /missione comment, o /missione follow.", reply_markup=MAIN_MENU)
            return
        filtro = {"tipo": tipo}

    completate = supabase.table("log_attivita").select("mission_id").eq("telegram_id", telegram_id).execute().data
    completate_ids = [x["mission_id"] for x in completate if "mission_id" in x]

    mission_query = supabase.table("missioni").select("*").eq("attiva", True)
    if filtro:
        mission_query = mission_query.eq("tipo", filtro["tipo"])
    if completate_ids:
        mission_query = mission_query.notin_("id", completate_ids)
    mission = mission_query.limit(1).execute()

    if not mission.data:
        await update.message.reply_text("⏳ Nessuna missione disponibile al momento.", reply_markup=MAIN_MENU)
        return
    m = mission.data[0]
    tipo = m['tipo']
    url = m['url']
    testo = f"🔔 Missione: {tipo.upper()} il post: {url}\nDopo aver eseguito, usa /verifica"
    await context.bot.send_message(chat_id=telegram_id, text=testo)

async def verifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Funzione per verificare il completamento della missione
    # (Simile al codice precedente)
    pass

async def punti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    punti = supabase.table("utenti").select("punti").eq("telegram_id", telegram_id).execute().data[0]["punti"]
    await update.message.reply_text(f"🎯 Hai {punti} punti!", reply_markup=MAIN_MENU)

async def getlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Funzione per generare il link referral
    # (Simile al codice precedente)
    pass

# Funzione principale con Webhook
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Aggiungi i gestori dei comandi
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("insta", insta))
    app.add_handler(CommandHandler("missione", missione))
    app.add_handler(CommandHandler("punti", punti))
    app.add_handler(CommandHandler("getlink", getlink))

    # Avvia il webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL
    )

if __name__ == '__main__':
    main()






import os
import logging
import instaloader
import requests
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from supabase import create_client, Client
from aiohttp import web  # Per healthcheck su Render

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Env Variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("TUO_TELEGRAM_ID_ADMIN", "0").strip())
CANAL_TELEGRAM_ID = os.getenv("CANAL_TELEGRAM_ID", "").strip()
WOOCOMMERCE_URL = os.getenv("WOOCOMMERCE_API_URL", "").strip()
WOOCOMMERCE_KEY = os.getenv("WOOCOMMERCE_KEY", "").strip()
WOOCOMMERCE_SECRET = os.getenv("WOOCOMMERCE_SECRET", "").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY", "").strip()

# Verifica variabili ambiente
if not all([BOT_TOKEN, SUPABASE_URL, SUPABASE_API_KEY]):
    raise ValueError("Variabili d'ambiente mancanti o errate.")

# Supabase setup
supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)

# Instaloader setup
L = instaloader.Instaloader()

# Menu principale
MAIN_MENU = ReplyKeyboardMarkup([ 
    ["/missione", "/verifica"], 
    ["/punti", "/getlink", "/help"]
], resize_keyboard=True)

# Comando aggiungi missione
async def aggiungi_missione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if telegram_id != ADMIN_ID:
        await update.message.reply_text("🚫 Non hai i permessi per creare missioni.")
        return

    if len(context.args) != 3:
        await update.message.reply_text("❌ Formato: /aggiungi_missione tipo url attiva (es. like https://... true).")
        return

    tipo, url, attiva = context.args[0].lower(), context.args[1], context.args[2].lower() == 'true'

    if tipo not in ["like", "comment", "follow"]:
        await update.message.reply_text("❌ Tipo non valido. Usa: like, comment, follow.")
        return

    try:
        supabase.table("missioni").insert({"tipo": tipo, "url": url, "attiva": attiva}).execute()
        msg = f"🔔 Nuova missione! Tipo: {tipo.upper()} su {url}\nCompleta con /verifica."
        await context.bot.send_message(chat_id=CANAL_TELEGRAM_ID, text=msg)
        await update.message.reply_text(f"✅ Missione {tipo} creata! URL: {url}", reply_markup=MAIN_MENU)
    except Exception as e:
        logging.error(f"Errore missione: {e}")
        await update.message.reply_text("⚠️ Errore durante la creazione. Riprova.")

# Verifica missione
def verifica_missione_completata(tipo, username, post_url):
    try:
        shortcode = post_url.rstrip("/").split("/")[-1]
        post = instaloader.Post.from_shortcode(L.context, shortcode)

        if tipo == "like":
            return any(like.username == username for like in post.get_likes())
        elif tipo == "comment":
            return any(comment.owner.username == username for comment in post.get_comments())
        elif tipo == "follow":
            return any(follower.username == username for follower in post.owner_profile.get_followers())
    except Exception as e:
        logging.error(f"Errore verifica missione: {e}")
    return False

# Comando verifica
async def verifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    try:
        missione = supabase.table("missioni").select("*").eq("attiva", True).limit(1).execute().data[0]
        tipo, url = missione["tipo"], missione["url"]

        username_instagram = supabase.table("utenti").select("username_instagram").eq("telegram_id", telegram_id).execute().data[0]["username_instagram"]

        if verifica_missione_completata(tipo, username_instagram, url):
            supabase.table("utenti").update({"punti": 1}).eq("telegram_id", telegram_id).execute()
            codice_sconto = f"CODICE-SCONTO-{telegram_id}"
            await update.message.reply_text(f"🎉 Missione completata! Codice sconto: {codice_sconto}", reply_markup=MAIN_MENU)
            requests.post(WOOCOMMERCE_URL, auth=(WOOCOMMERCE_KEY, WOOCOMMERCE_SECRET), data={"coupon_code": codice_sconto})
        else:
            await update.message.reply_text("❌ Missione non completata. Riprova.", reply_markup=MAIN_MENU)
    except Exception as e:
        logging.error(f"Errore verifica: {e}")
        await update.message.reply_text("⚠️ Errore durante la verifica. Riprova più tardi.", reply_markup=MAIN_MENU)

# Comando start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Benvenuto! Usa /missione per iniziare e /verifica per completare.", reply_markup=MAIN_MENU)

# Comando help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "I comandi disponibili:\n"
        "/missione - Vedi missioni\n"
        "/verifica - Verifica missione\n"
        "/punti - I tuoi punti\n"
        "/getlink - Link referral\n"
        "/help - Aiuto",
        reply_markup=MAIN_MENU
    )

# Webhook
async def set_webhook(application):
    webhook_url = os.getenv("WEBHOOK_URL", "").strip()
    if webhook_url:
        await application.bot.set_webhook(url=webhook_url)
    else:
        logging.error("URL Webhook non configurato!")

# Main
async def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("aggiungi_missione", aggiungi_missione))
    application.add_handler(CommandHandler("verifica", verifica))

    # Run the webhook (using aiohttp for Render)
    runner = web.AppRunner(application)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "5000")))
    await site.start()

    # Keep the app running
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())





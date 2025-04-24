import os
import logging
import instaloader
import requests
from urllib.parse import urlparse
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from supabase import create_client, Client

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
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
PORT = int(os.getenv("PORT", "8443").strip())
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY", "").strip()

# Verifica che tutte le variabili siano configurate
if not all([BOT_TOKEN, SUPABASE_URL, SUPABASE_API_KEY, WEBHOOK_URL]):
    raise ValueError("Alcune variabili d'ambiente sono mancanti o non configurate correttamente.")

# Supabase setup
supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)

# Instaloader setup
L = instaloader.Instaloader()

# Menu
MAIN_MENU = ReplyKeyboardMarkup([
    ["/missione", "/verifica"],
    ["/punti", "/getlink", "/help"]
], resize_keyboard=True)

# Funzione di verifica missione
def verifica_missione_completata(tipo, username, post):
    try:
        if tipo == "like":
            return username in [like.username for like in post.get_likes()]
        elif tipo == "follow":
            return username in [f.username for f in post.owner_profile.get_followers()]
        elif tipo == "comment":
            return username in [c.owner.username for c in post.get_comments()]
    except Exception as e:
        logging.error(f"Errore durante la verifica della missione: {e}")
        return False
    return False

# Comandi del bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    try:
        user = supabase.table("utenti").select("*").eq("telegram_id", telegram_id).execute()
        if not user.data:
            supabase.table("utenti").insert({"telegram_id": telegram_id, "punti": 0}).execute()
            await update.message.reply_text(
                "👋 Benvenuto nel bot missioni! Usa /insta <username> per collegare Instagram.",
                reply_markup=MAIN_MENU
            )
        else:
            await update.message.reply_text("Bentornato! 🎉", reply_markup=MAIN_MENU)
    except Exception as e:
        logging.error(f"Errore durante la registrazione dell'utente: {e}")
        await update.message.reply_text("⚠️ Si è verificato un errore. Riprova più tardi.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Comandi:\n"
        "/start - Registrazione\n"
        "/insta <username> - Collega Instagram\n"
        "/missione [tipo] - Ricevi una missione (like, comment, follow)\n"
        "/verifica - Verifica completamento\n"
        "/punti - Punti attuali\n"
        "/getlink - Ottieni il tuo link referral",
        reply_markup=MAIN_MENU
    )

async def insta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if len(context.args) != 1:
        await update.message.reply_text("❌ Usa /insta tuo_username", reply_markup=MAIN_MENU)
        return
    try:
        supabase.table("utenti").update({"username_instagram": context.args[0]}).eq("telegram_id", telegram_id).execute()
        await update.message.reply_text(f"✅ Username Instagram impostato: {context.args[0]}", reply_markup=MAIN_MENU)
    except Exception as e:
        logging.error(f"Errore durante l'aggiornamento dell'username Instagram: {e}")
        await update.message.reply_text("⚠️ Errore durante l'aggiornamento dell'username. Riprova più tardi.")

async def missione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_type = update.effective_chat.type

    # Verifica che il comando venga usato in chat privata
    if chat_type != "private":
        await update.message.reply_text("❗ Per ricevere missioni usa questo comando in chat privata.")
        return

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

    try:
        completate = supabase.table("log_attivita").select("mission_id").eq("telegram_id", telegram_id).execute().data
        completate_ids = [x["mission_id"] for x in completate if "mission_id" in x]

        mission_query = supabase.table("missioni").select("*").eq("attiva", True)
        if filtro:
            mission_query = mission_query.eq("tipo", filtro["tipo"])
        if completate_ids:
            mission_query = mission_query.notin_("id", completate_ids)
        missioni = mission_query.execute().data

        if not missioni:
            await update.message.reply_text("⏳ Nessuna missione disponibile al momento.", reply_markup=MAIN_MENU)
            return

        for m in missioni:
            tipo = m['tipo']
            url = m['url']
            testo = f"🔔 Missione: {tipo.upper()} il post:\n{url}\n✅ Dopo aver eseguito, usa /verifica"
            await context.bot.send_message(chat_id=telegram_id, text=testo)

    except Exception as e:
        logging.error(f"Errore durante il recupero delle missioni: {e}")
        await update.message.reply_text("⚠️ Si è verificato un errore nel recupero delle missioni. Riprova più tardi.")


async def punti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    try:
        punti = supabase.table("utenti").select("punti").eq("telegram_id", telegram_id).execute().data[0]["punti"]
        await update.message.reply_text(f"🎯 Hai {punti} punti!", reply_markup=MAIN_MENU)
    except Exception as e:
        logging.error(f"Errore durante il recupero dei punti: {e}")
        await update.message.reply_text("⚠️ Errore durante il recupero dei punti. Riprova più tardi.")

# Funzione per creare missioni
async def crea_missione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id

    if telegram_id != ADMIN_ID:
        await update.message.reply_text("❌ Solo l'amministratore può creare missioni.", reply_markup=MAIN_MENU)
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usa il formato: /crea_missione <tipo> <url>\n"
            "Esempio corretto: /crea_missione like https://www.instagram.com/p/xxxxxx",
            reply_markup=MAIN_MENU
        )
        return

    tipo = context.args[0].lower()
    url = context.args[1]

    if tipo not in ["like", "comment", "follow"]:
        await update.message.reply_text(
            "❌ Tipo non valido. Usa: like, comment, or follow.\n"
            "Esempio corretto: /crea_missione like https://www.instagram.com/p/xxxxxx",
            reply_markup=MAIN_MENU
        )
        return

    try:
        data_creazione = datetime.now().isoformat()  # Converte la data in formato ISO 8601
        missione = {
            "tipo": tipo,
            "url": url,
            "attiva": True,
            "data_creazione": data_creazione
        }

        supabase.table("missioni").insert(missione).execute()
        await update.message.reply_text(f"✅ Missione '{tipo}' creata con successo: {url}", reply_markup=MAIN_MENU)
    except Exception as e:
        logging.error(f"Errore durante la creazione della missione: {e}")
        await update.message.reply_text("⚠️ Errore durante la creazione della missione. Riprova più tardi.", reply_markup=MAIN_MENU)
# Funzione principale con Webhook
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Aggiungi i gestori dei comandi
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("insta", insta))
    app.add_handler(CommandHandler("missione", missione))
    app.add_handler(CommandHandler("punti", punti))
    app.add_handler(CommandHandler("crea_missione", crea_missione))  # Nuovo comando per creare missione

    # Avvia il webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL
    )

if __name__ == '__main__':
    main()


if __name__ == '__main__':
    main()







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
    try:
        # Verifica se l'utente è nel gruppo o nella chat privata
        is_private_chat = update.message.chat.type == 'private'  # Verifica se è chat privata

        # Filtro missioni da completare
        completate = supabase.table("log_attivita").select("mission_id").eq("telegram_id", telegram_id).execute().data
        completate_ids = [x["mission_id"] for x in completate if "mission_id" in x]

        mission_query = supabase.table("missioni").select("*").eq("attiva", True)
        if completate_ids:
            mission_query = mission_query.notin_("id", completate_ids)
        missioni = mission_query.execute().data

        if not missioni:
            await update.message.reply_text("⏳ Nessuna missione disponibile al momento.", reply_markup=MAIN_MENU)
            return
        
        # Se il comando è eseguito nel gruppo, rispondi in privato una sola volta
        if not is_private_chat:
            await update.message.reply_text("🔔 Ti ho inviato le missioni in chat privata.", reply_markup=MAIN_MENU)

        # Ciclo per inviare tutte le missioni
        for m in missioni:
            tipo = m['tipo']
            url = m['url']
            testo = f"🔔 Missione: {tipo.upper()} il post: {url}\nDopo aver eseguito, usa /verifica"
            
            # Invia il messaggio in chat privata
            await context.bot.send_message(chat_id=telegram_id, text=testo)

    except Exception as e:
        logging.error(f"Errore durante il recupero delle missioni: {e}")
        await update.message.reply_text("⚠️ Si è verificato un errore nel recupero delle missioni. Riprova più tardi.")

async def verifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    try:
        completate = supabase.table("log_attivita").select("mission_id").eq("telegram_id", telegram_id).execute().data
        completate_ids = [x["mission_id"] for x in completate if "mission_id" in x]
        
        mission_query = supabase.table("missioni").select("*").eq("attiva", True)
        if completate_ids:
            mission_query = mission_query.notin_("id", completate_ids)
        missioni = mission_query.execute().data
        
        if not missioni:
            await update.message.reply_text("⏳ Non ci sono missioni attive da verificare.", reply_markup=MAIN_MENU)
            return

        # Verifica le missioni
        for missione in missioni:
            tipo = missione['tipo']
            url = missione['url']
            testo = f"🔍 Sto verificando la missione: {tipo.upper()} il post {url}..."
            await update.message.reply_text(testo, reply_markup=MAIN_MENU)

            try:
                # Estrae l'ID del post dall'URL
                shortcode = urlparse(url).path.split('/')[-2]
                
                # Usa il shortcode per ottenere il post
                post = instaloader.Post.from_shortcode(L.context, shortcode)
                
                # Ottieni lo username Instagram dall'utente
                username_instagram = supabase.table("utenti").select("username_instagram").eq("telegram_id", telegram_id).execute().data
                if not username_instagram:
                    raise Exception("Username Instagram non trovato per questo utente.")
                username_instagram = username_instagram[0]["username_instagram"]
                
                # Verifica se la missione è completata
                completato = verifica_missione_completata(tipo, username_instagram, post)

                # Rispondi in base alla verifica della missione
                if completato:
                    # Aggiungi la missione come completata
                    supabase.table("log_attivita").insert({"telegram_id": telegram_id, "mission_id": missione["id"]}).execute()
                    await update.message.reply_text(f"✅ Missione completata: {tipo.upper()} il post {url}", reply_markup=MAIN_MENU)
                else:
                    await update.message.reply_text(f"❌ Missione non completata: {tipo.upper()} il post {url}", reply_markup=MAIN_MENU)
            except Exception as e:
                logging.error(f"Errore durante la verifica della missione: {e}")
                await update.message.reply_text("⚠️ Si è verificato un errore nella verifica della missione. Riprova più tardi.")

# Funzione per recuperare i punti dell'utente
async def punti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    try:
        # Recupera i punti dell'utente
        punti = supabase.table("utenti").select("punti").eq("telegram_id", telegram_id).execute().data
        if not punti:
            raise Exception("Punti non trovati per l'utente.")
        punti = punti[0]["punti"]
        
        # Rispondi con il numero di punti
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
            "Esempio corretto: /crea_missione like https://www.instagram.com/p/abc123/",
            reply_markup=MAIN_MENU
        )
        return
ipo = context.args[0].lower()
    url = context.args[1]
    try:
        data_creazione = datetime.now().isoformat()  # Converte la data in formato ISO 8601
        missione = {
            "tipo": tipo,
            "url": url,
            "attiva": True,
            "data_creazione": data_creazione
        }

       # Aggiungi la missione nel database
    try:
        missione = supabase.table("missioni").insert({"tipo": tipo, "url": url, "attiva": True}).execute()
        await update.message.reply_text(f"✅ Missione '{tipo}' creata con successo.", reply_markup=MAIN_MENU)
    except Exception as e:
        logging.error(f"Errore durante la creazione della missione: {e}")
        await update.message.reply_text("⚠️ Errore durante la creazione della missione. Riprova più tardi.")

# Funzione principale con Webhook
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Aggiungi i gestori dei comandi
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("insta", insta))
    app.add_handler(CommandHandler("missione", missione))
    app.add_handler(CommandHandler("punti", punti))
    app.add_handler(CommandHandler("verifica", verifica))
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







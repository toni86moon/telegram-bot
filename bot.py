import os
import logging
import instaloader
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from supabase import create_client, Client
from telegram.ext import Dispatcher, Update
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters

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

# Verifica che tutte le variabili siano configurate
if not all([BOT_TOKEN, SUPABASE_URL, SUPABASE_API_KEY]):
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

# Comando per aggiungere una missione (solo per amministratori)
async def aggiungi_missione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id

    # Controlla che l'utente sia l'amministratore
    if telegram_id != ADMIN_ID:
        await update.message.reply_text("🚫 Non hai i permessi per creare missioni.")
        return

    # Verifica che i parametri siano corretti
    if len(context.args) != 3:
        await update.message.reply_text("❌ Usa il formato corretto: /aggiungi_missione tipo url attiva (es. like https://instagram.com/post true).")
        return

    tipo = context.args[0].lower()  # tipo della missione (like, comment, follow)
    url = context.args[1]  # URL del post Instagram
    attiva = context.args[2].lower() == 'true'  # Stato della missione (attiva o no)

    # Verifica che il tipo della missione sia valido
    if tipo not in ["like", "comment", "follow"]:
        await update.message.reply_text("❌ Tipo non valido. Usa: like, comment, o follow.")
        return

    try:
        # Inserisci la missione nel database
        supabase.table("missioni").insert({"tipo": tipo, "url": url, "attiva": attiva}).execute()
        
        # Notifica la missione a tutti i membri del gruppo
        message = f"🔔 Nuova missione disponibile! Tipo: {tipo.upper()} su {url}\nCompleta la missione con /verifica."
        await context.bot.send_message(chat_id=CANAL_TELEGRAM_ID, text=message)
        
        await update.message.reply_text(f"✅ Missione {tipo} creata con successo! URL: {url}", reply_markup=MAIN_MENU)
    except Exception as e:
        logging.error(f"Errore durante la creazione della missione: {e}")
        await update.message.reply_text("⚠️ Errore durante la creazione della missione. Riprova più tardi.")

# Funzione di verifica missione completata
def verifica_missione_completata(tipo, username, post_url):
    try:
        post = L.get_post_from_url(post_url)
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

# Comando per la verifica
async def verifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    try:
        # Recupera l'ultima missione per l'utente
        missione = supabase.table("missioni").select("*").eq("attiva", True).limit(1).execute().data[0]
        tipo = missione['tipo']
        url = missione['url']
        
        # Verifica tramite Instaloader
        username_instagram = supabase.table("utenti").select("username_instagram").eq("telegram_id", telegram_id).execute().data[0]["username_instagram"]
        if verifica_missione_completata(tipo, username_instagram, url):
            # Missione completata: assegna il punteggio e invia il codice sconto
            supabase.table("utenti").update({"punti": 1}).eq("telegram_id", telegram_id).execute()
            codice_sconto = f"CODICE-SCONTO-{telegram_id}"
            await update.message.reply_text(f"🎉 Missione completata! Hai guadagnato 1 punto. Usa il codice sconto: {codice_sconto}", reply_markup=MAIN_MENU)

            # Invia il codice sconto tramite WooCommerce API (esempio)
            requests.post(WOOCOMMERCE_URL, auth=(WOOCOMMERCE_KEY, WOOCOMMERCE_SECRET), data={"coupon_code": codice_sconto})
        else:
            await update.message.reply_text("❌ Missione non completata correttamente. Riprova con /verifica dopo aver eseguito l'azione.", reply_markup=MAIN_MENU)
    except Exception as e:
        logging.error(f"Errore durante la verifica della missione: {e}")
        await update.message.reply_text("⚠️ Si è verificato un errore. Riprova più tardi.", reply_markup=MAIN_MENU)

# Configura il webhook
async def set_webhook(application):
    webhook_url = os.getenv("WEBHOOK_URL", "").strip()  # Set Webhook URL
    if webhook_url:
        await application.bot.set_webhook(url=webhook_url)
    else:
        logging.error("URL del webhook non configurato!")

# Funzione di start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Benvenuto! Usa /missione per vedere le missioni disponibili e /verifica per completarle.",
        reply_markup=MAIN_MENU
    )

# Funzione di aiuto
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "I comandi disponibili sono:\n"
        "/missione - Visualizza le missioni disponibili\n"
        "/verifica - Verifica se hai completato una missione\n"
        "/punti - Vedi i tuoi punti\n"
        "/getlink - Ottieni il tuo link referral\n"
        "/help - Mostra questa guida",
        reply_markup=MAIN_MENU
    )

# Funzione di esecuzione principale
def main():
    # Crea l'applicazione Telegram
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Aggiungi i handler dei comandi
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("aggiungi_missione", aggiungi_missione))
    application.add_handler(CommandHandler("verifica", verifica))

    # Configura il webhook
    set_webhook(application)

    # Avvia l'applicazione con il webhook
    application.run_webhook(listen="0.0.0.0", port=int(os.getenv("PORT", "5000")), url_path=BOT_TOKEN)

if __name__ == '__main__':
    main()





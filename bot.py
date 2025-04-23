import os
import logging
import instaloader
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from supabase import create_client
from dotenv import load_dotenv

# Carica variabili d'ambiente dal file .env
load_dotenv()

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_API_KEY)

# Instaloader setup
L = instaloader.Instaloader()

# Funzione per verificare interazioni Instagram (like, commenti, follow)
def verifica_instagram(username_insta, tipo_missione):
    try:
        profile = instaloader.Profile.from_username(L.context, username_insta)
        
        # Esegui la verifica in base al tipo di missione
        if tipo_missione == "like":
            # Logica per verificare se l'utente ha messo like a un determinato post
            post_url = os.getenv("INSTAGRAM_POST_URL")  # URL del post da controllare
            post = instaloader.Post.from_url(L.context, post_url)
            return post.likes_count > 0  # Verifica se ci sono like (potresti migliorare con un controllo sugli utenti che hanno messo like)

        elif tipo_missione == "commento":
            # Logica per verificare se l'utente ha commentato su un post
            post_url = os.getenv("INSTAGRAM_POST_URL")  # URL del post da controllare
            post = instaloader.Post.from_url(L.context, post_url)
            for comment in post.get_comments():
                if comment.owner.username == username_insta:
                    return True
            return False
        
        elif tipo_missione == "follow":
            # Logica per verificare se l'utente segue un account specifico
            account_da_seguire = os.getenv("INSTAGRAM_ACCOUNT_TO_FOLLOW")  # Account che l'utente deve seguire
            account = instaloader.Profile.from_username(L.context, account_da_seguire)
            return profile.followed_by(account)  # Verifica se il profilo segue l'account

        return False  # Se non corrisponde a nessun tipo di missione

    except instaloader.exceptions.InstaloaderException as e:
        logging.error(f"Errore durante il caricamento del profilo Instagram: {e}")
        return False

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    username = update.effective_user.username

    user = supabase.table("utenti").select("*").eq("telegram_id", telegram_id).execute()
    if not user.data:
        supabase.table("utenti").insert({
            "telegram_id": telegram_id,
            "username_instagram": None
        }).execute()
        await update.message.reply_text("👋 Benvenuto nel nostro bot di missioni su Instagram!")
    else:
        await update.message.reply_text("Bentornato! 🎉")

# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Comandi disponibili:\n"
        "/start - Registrazione\n"
        "/insta <tuo_utente_instagram> - Imposta il tuo username Instagram\n"
        "/verifica <tipo_missione> - Controlla se hai completato la missione (like, commento, follow)\n"
        "/punti - Mostra i tuoi punti attuali"
    )

# /insta
async def insta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if len(context.args) != 1:
        await update.message.reply_text("❌ Usa il comando così: /insta tuo_username")
        return
    username_insta = context.args[0]
    supabase.table("utenti").update({"username_instagram": username_insta}).eq("telegram_id", telegram_id).execute()
    await update.message.reply_text(f"✅ Username Instagram impostato: {username_insta}")

# /verifica
async def verifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if len(context.args) != 1 or context.args[0] not in ["like", "commento", "follow"]:
        await update.message.reply_text("❌ Usa il comando così: /verifica <like/commento/follow>")
        return
    
    tipo_missione = context.args[0]
    user = supabase.table("utenti").select("username_instagram").eq("telegram_id", telegram_id).execute()

    if user.data:
        username_insta = user.data[0]["username_instagram"]
        if username_insta and verifica_instagram(username_insta, tipo_missione):
            supabase.table("log_attivita").insert({
                "telegram_id": telegram_id,
                "evento": "verifica",
                "descrizione": f"La missione '{tipo_missione}' è stata completata."
            }).execute()
            await update.message.reply_text(f"🎉 Missione '{tipo_missione}' completata! Hai guadagnato dei punti.")
            supabase.table("utenti").update({"punti": 10}).eq("telegram_id", telegram_id).execute()  # Aggiungi punti
        else:
            await update.message.reply_text(f"❌ La missione '{tipo_missione}' non è stata completata. Assicurati di aver interagito correttamente.")
            supabase.table("log_attivita").insert({
                "telegram_id": telegram_id,
                "evento": "verifica",
                "descrizione": f"Tentativo di completare la missione '{tipo_missione}' fallito."
            }).execute()
    else:
        await update.message.reply_text("⚠️ Non sei registrato. Usa /start per iniziare.")

# /punti
async def punti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = supabase.table("utenti").select("punti").eq("telegram_id", telegram_id).execute()
    if user.data:
        punteggio = user.data[0]["punti"]
        await update.message.reply_text(f"🏆 Hai {punteggio} punti.")
    else:
        await update.message.reply_text("⚠️ Non sei registrato. Usa /start per iniziare.")

# Comando sconosciuto
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Comando non riconosciuto. Scrivi /help per vedere la lista.")

# Gestione errori
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(msg="Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("❌ Si è verificato un errore imprevisto. Riprova più tardi.")

# Avvio del bot
if __name__ == '__main__':
    import asyncio
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    async def main():
        app = ApplicationBuilder().token(BOT_TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("insta", insta))
        app.add_handler(CommandHandler("verifica", verifica))
        app.add_handler(CommandHandler("punti", punti))
        app.add_handler(MessageHandler(filters.COMMAND, unknown))

        app.add_error_handler(error_handler)

        print("✅ Bot avviato")
        await app.run_polling()

    asyncio.run(main())






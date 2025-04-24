import os
import logging
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
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
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
PORT = int(os.getenv("PORT", "8443").strip())
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY", "").strip()

# Verifica che tutte le variabili siano configurate
if not all([BOT_TOKEN, SUPABASE_URL, SUPABASE_API_KEY, WEBHOOK_URL]):
    raise ValueError("Alcune variabili d'ambiente sono mancanti o non configurate correttamente.")

# Supabase setup
supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)

# Stati per il comando aggiungi_missione
TIPO, URL = range(2)

# Menu
MAIN_MENU = ReplyKeyboardMarkup([ 
    ["/missione", "/verifica"], 
    ["/punti", "/getlink", "/help"]
], resize_keyboard=True)

# Funzione per aggiungere una missione
async def aggiungi_missione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id

    # Verifica se l'utente è l'amministratore
    if telegram_id != ADMIN_ID:
        await update.message.reply_text("❌ Solo l'amministratore può aggiungere missioni.")
        return ConversationHandler.END

    await update.message.reply_text("Inserisci il tipo di missione (like, comment, follow):")
    return TIPO

async def ricevi_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tipo = update.message.text.lower()

    # Verifica il tipo di missione
    if tipo not in ["like", "comment", "follow"]:
        await update.message.reply_text("❌ Tipo non valido. Usa: like, comment, o follow.")
        return TIPO

    # Memorizza il tipo di missione nel contesto
    context.user_data["tipo"] = tipo
    await update.message.reply_text("Ora inserisci l'URL del post Instagram:")
    return URL

async def ricevi_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    tipo = context.user_data["tipo"]

    try:
        # Inserisci la missione nel database
        response = supabase.table("missioni").insert({
            "tipo": tipo,
            "url": url,
            "attiva": True
        }).execute()

        missione_id = response.data[0]["id"]

        # Conferma all'amministratore
        await update.message.reply_text(f"✅ Missione aggiunta con successo:\nTipo: {tipo}\nURL: {url}", reply_markup=MAIN_MENU)

        # Crea i pulsanti per la notifica
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Accetta missione", callback_data=f"accetta_{missione_id}")]
        ])

        # Invia al gruppo
        await context.bot.send_message(
            chat_id=CANAL_TELEGRAM_ID,
            text=f"🚀 *Nuova missione disponibile!*\n\n📌 Tipo: *{tipo}*\n🔗 URL: {url}",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    except Exception as e:
        logging.error(f"Errore durante l'aggiunta della missione: {e}")
        await update.message.reply_text("⚠️ Si è verificato un errore durante l'aggiunta della missione. Riprova più tardi.")

    return ConversationHandler.END

async def annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operazione annullata.", reply_markup=MAIN_MENU)
    return ConversationHandler.END

# Funzione di callback per accettare la missione
async def accetta_missione_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    username = query.from_user.username
    data = query.data

    if not data.startswith("accetta_"):
        return

    missione_id = int(data.split("_")[1])

    try:
        # Salva accettazione missione
        supabase.table("accettazioni").insert({
            "user_id": user_id,
            "username": username,
            "missione_id": missione_id
        }).execute()

        await query.edit_message_reply_markup(None)
        await query.message.reply_text(
            f"🎯 @{username}, hai accettato la missione #{missione_id}! Buon lavoro! 💪"
        )

    except Exception as e:
        logging.error(f"Errore accettazione missione: {e}")
        await query.message.reply_text("⚠️ Errore durante l'accettazione della missione.")

# Comandi esistenti ripristinati
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

# Funzione principale con Webhook
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Gestore per aggiungere missioni
    aggiungi_missione_handler = ConversationHandler(
        entry_points=[CommandHandler("aggiungi_missione", aggiungi_missione)],
        states={TIPO: [MessageHandler(filters.TEXT & ~filters.COMMAND, ricevi_tipo)],
                URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ricevi_url)]},
        fallbacks=[CommandHandler("annulla", annulla)],
    )

    # Aggiungi i gestori dei comandi
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("missione", missione))
    app.add_handler(CommandHandler("punti", punti))
    app.add_handler(CommandHandler("verifica", verifica))
    app.add_handler(CommandHandler("getlink", getlink))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(aggiungi_missione_handler)
    app.add_handler(CallbackQueryHandler(accetta_missione_callback))

    # Avvia il webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL
    )

if __name__ == '__main__':
    main()






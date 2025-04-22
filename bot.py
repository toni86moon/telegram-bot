import logging
import asyncio
from telegram import Bot, Update
from telegram.ext import CommandHandler, MessageHandler, Filters, Updater, CallbackContext, Application
from telegram.ext import Dispatcher
from requests.exceptions import Timeout
import requests

# Impostazioni di logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Variabili per il bot Telegram
TOKEN = "YOUR_BOT_TOKEN"
WEBHOOK_URL = "YOUR_WEBHOOK_URL"

# Funzione di start
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Ciao! Sono il tuo bot. Come posso aiutarti?')

# Funzione di help
async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Questi sono i comandi disponibili:\n/start - per avviare il bot\n/help - per visualizzare questo messaggio')

# Funzione per creare una missione
async def crea_missione(update: Update, context: CallbackContext) -> None:
    try:
        if len(context.args) < 1:
            await update.message.reply_text('Devi specificare un link per creare una missione!')
            return
        
        link = context.args[0]
        # Aggiungi logica per trattare il link
        await update.message.reply_text(f'Missione creata con il link: {link}')

    except Exception as e:
        logger.error(f"Errore durante la creazione della missione: {e}")
        await update.message.reply_text('Si è verificato un errore durante la creazione della missione.')

# Funzione di gestione degli errori
async def handle_error(update: Update, context: CallbackContext):
    try:
        logger.error(f'Errore: {context.error}')
        await update.message.reply_text('Si è verificato un errore durante l\'elaborazione della richiesta.')
    except Exception as e:
        logger.error(f'Errore durante la gestione dell\'errore: {e}')

# Funzione per impostare il bot Telegram
async def setup_bot():
    application = Application.builder().token(TOKEN).build()

    # Aggiungi handler per i comandi
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("crea_missione", crea_missione))

    # Aggiungi handler per gli errori
    application.add_error_handler(handle_error)

    # Impostazione del webhook
    bot = Bot(TOKEN)
    bot.set_webhook(url=WEBHOOK_URL)

    return application

# Funzione per avviare il bot
async def run_bot():
    try:
        application = await setup_bot()
        await application.run_polling(allowed_updates=Update.ALL)
    except Timeout as e:
        logger.error(f'Errore di timeout: {e}')
    except Exception as e:
        logger.error(f'Errore durante l\'avvio del bot: {e}')

# Avvia il bot
if __name__ == "__main__":
    asyncio.run(run_bot())






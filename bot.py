import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# --- COSTANTI ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # L'URL pubblico del tuo bot (es. https://<render-app>.onrender.com)

if not BOT_TOKEN:
    raise ValueError("La variabile d'ambiente BOT_TOKEN non è configurata. Assicurati di fornire un token valido del bot.")

if not WEBHOOK_URL:
    raise ValueError("La variabile d'ambiente WEBHOOK_URL non è configurata. Assicurati di fornire un URL pubblico valido per il webhook.")

# --- FLASK SERVER ---
app = Flask(__name__)
telegram_app = None  # Variabile globale per l'app Telegram

@app.route("/", methods=["GET"])
def home():
    """Endpoint per verificare che il bot sia attivo."""
    return "Il bot è attivo e in esecuzione."

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    """Gestisce le richieste in arrivo da Telegram."""
    if telegram_app:
        try:
            update_data = request.get_json(force=True)
            if not update_data:
                print("⚠️ Nessun dato ricevuto nell'aggiornamento.")
                return "Bad Request", 400

            print(f"📩 Dati aggiornamento ricevuti: {update_data}")  # Log dettagliato dei dati ricevuti
            update = Update.de_json(update_data, telegram_app.bot)
            print(f"✅ Oggetto aggiornamento de-serializzato: {update.to_dict()}")  # Log dell'oggetto aggiornamento

            # Avvia un thread separato per processare l'aggiornamento
            from threading import Thread
            Thread(target=telegram_app.update_queue.put_nowait, args=(update,)).start()
        except Exception as e:
            print(f"❌ Errore durante il webhook: {e}")  # Log degli errori
            return "Internal Server Error", 500
    return "OK", 200

# --- FUNZIONI DEL BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il comando /start."""
    try:
        print("📢 Comando /start ricevuto")  # Log del comando ricevuto
        await update.message.reply_text("Ciao! Sono attivo e pronto ad aiutarti.")
    except Exception as e:
        print(f"❌ Errore durante l'invio del messaggio /start: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il comando /help."""
    try:
        print("📢 Comando /help ricevuto")  # Log del comando ricevuto
        await update.message.reply_text("Ecco i comandi disponibili:\n/start - Avvia il bot\n/help - Mostra questo messaggio")
    except Exception as e:
        print(f"❌ Errore durante l'invio del messaggio /help: {e}")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Risponde ai messaggi di testo generici."""
    try:
        user_message = update.message.text.strip()
        if not user_message:
            await update.message.reply_text("Non ho capito il tuo messaggio. Prova a scrivere qualcosa!")
        else:
            await update.message.reply_text(f"Hai detto: {user_message}")
    except Exception as e:
        print(f"❌ Errore durante l'invio della risposta: {e}")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Risponde ai comandi sconosciuti."""
    try:
        print(f"❓ Comando sconosciuto ricevuto: {update.message.text}")  # Log del comando sconosciuto
        await update.message.reply_text("Mi dispiace, non riconosco questo comando. Usa /help per vedere i comandi disponibili.")
    except Exception as e:
        print(f"❌ Errore durante l'invio della risposta per comando sconosciuto: {e}")

# --- GESTIONE ERRORI ---
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log degli errori."""
    print(f"❌ Errore: {context.error}")
    if update:
        print(f"🔍 Contesto dell'aggiornamento: {update.to_dict()}")
    if update and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Si è verificato un errore interno. Riprova più tardi."
            )
        except Exception as e:
            print(f"⚠️ Impossibile notificare l'utente dell'errore: {e}")

# --- CONFIGURAZIONE DEL BOT ---
async def main():
    global telegram_app
    telegram_app = Application.builder().token(BOT_TOKEN).build()

    # Aggiungi handler
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    telegram_app.add_handler(MessageHandler(filters.COMMAND, unknown))  # Catch-all per comandi non riconosciuti

    # Aggiungi gestore degli errori
    telegram_app.add_error_handler(error_handler)

    # Configura il webhook
    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    print(f"✅ Webhook configurato su: {WEBHOOK_URL}/{BOT_TOKEN}")

    try:
        print("🚀 Bot in esecuzione...")
        await telegram_app.start()
        await asyncio.Event().wait()
    except Exception as e:
        print(f"❌ Errore durante l'esecuzione del bot: {e}")
    finally:
        print("🛑 Arresto del bot...")
        await telegram_app.stop()

# --- AVVIO ---
if __name__ == "__main__":
    # Assicurarsi che il loop asyncio sia compatibile
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Avvia il server Flask in un thread separato
    from threading import Thread
    flask_thread = Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": 5000})
    flask_thread.start()

    # Avvia il bot
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("🛑 Arresto del bot...")
    finally:
        loop.run_until_complete(telegram_app.stop())
        loop.close()

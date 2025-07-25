import os
import sys
import json
import asyncio
import threading
import time
import requests
from flask import Flask, request
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from telegram.error import RetryAfter
from datetime import datetime
from vangelo_sender import invia_vangelo_oggi

# --- 1. Loop globale ---
main_loop = asyncio.new_event_loop()
asyncio.set_event_loop(main_loop)

# --- 2. Configurazioni ---
TOKEN = os.getenv("TOKEN")
WEBHOOK_PATH = f"/bot/{TOKEN}"
RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME", "localhost")
WEBHOOK_URL = f"https://{RENDER_HOST}{WEBHOOK_PATH}"

# --- 3. Flask app + bot ---
app = Flask(__name__)
bot_app = Application.builder().token(TOKEN).build()

# --- 4. Bottoni inline ---
def get_vangelo_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Vangelo del giorno", callback_data="vangelo_oggi")]
    ])

# --- 5. Funzione per inviare bottone iniziale ---
async def handle_vangelo_entry(chat_id):
    await bot_app.bot.send_message(
        chat_id,
        "Benvenuto! Clicca il bottone per ricevere il Vangelo del giorno 👇",
        reply_markup=get_vangelo_keyboard()
    )

# --- 6. Comando /vangelo [opzionale: data] ---
async def vangelo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📥 Comando /vangelo ricevuto", flush=True)
    chat_id = str(update.effective_chat.id)

    date_str = None
    if context.args:
        date_str = context.args[0]
        print(f"📅 Parametro data richiesto: {date_str}", flush=True)

    try:
        await update.message.reply_text("📨 Recupero il Vangelo richiesto...")
        await invia_vangelo_oggi(chat_id, TOKEN, date_str)

        await bot_app.bot.send_message(
            chat_id,
            "Puoi richiedere di nuovo il Vangelo qui sotto 👇",
            reply_markup=get_vangelo_keyboard()
        )

    except ValueError as ve:
        await update.message.reply_text(f"⚠️ Errore: {ve}")
    except Exception as e:
        print(f"❌ Errore in /vangelo: {e}", file=sys.stderr, flush=True)
        await update.message.reply_text("⚠️ Errore durante l'invio del Vangelo.")

# --- 7. Comando /start (anche con link ?start=vangelo) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"▶️ Comando /start ricevuto. Argomenti: {context.args}", flush=True)
    chat_id = update.effective_chat.id

    if context.args and context.args[0].startswith("vangelo"):
        await handle_vangelo_entry(chat_id)
    else:
        await update.message.reply_text(
            "Benvenuto! Clicca qui sotto per leggere il Vangelo:",
            reply_markup=get_vangelo_keyboard()
        )

# --- 8. Callback da bottone inline ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = str(query.message.chat.id)

    try:
        await query.answer()
        await query.edit_message_text("📨 Recupero il Vangelo richiesto...")
        await invia_vangelo_oggi(chat_id, TOKEN, None)

        await bot_app.bot.send_message(
            chat_id,
            "Puoi richiedere di nuovo il Vangelo qui sotto 👇",
            reply_markup=get_vangelo_keyboard()
        )

    except Exception as e:
        print(f"❌ Errore nella callback: {e}", file=sys.stderr, flush=True)
        await bot_app.bot.send_message(
            chat_id,
            "⚠️ Il bot si stava riattivando. Per favore clicca di nuovo tra pochi secondi 🙏"
        )

# --- 9. Handlers ---
bot_app.add_handler(CommandHandler("vangelo", vangelo))
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(handle_callback))

# --- 10. Webhook endpoint ---
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    print("📍 ENTRATO IN /bot/ webhook", flush=True)
    try:
        payload = request.get_json(force=True)
        print("📩 JSON ricevuto:\n" + json.dumps(payload, indent=2), flush=True)

        update = Update.de_json(payload, bot_app.bot)
        asyncio.run_coroutine_threadsafe(bot_app.process_update(update), main_loop)

        return "OK", 200
    except Exception as e:
        print("❌ Errore nel webhook:", e, file=sys.stderr, flush=True)
        return "Errore interno", 500

# --- 11. Endpoint ping ---
@app.route("/ping")
def ping():
    return "pong", 200

# --- 12. Endpoint wake_and_reset ---
@app.route("/wake_and_reset")
def wake_and_reset():
    def background_task():
        try:
            ping_url = f"https://{RENDER_HOST}/ping"
            max_wait_time = 60
            check_interval = 5
            elapsed = 0

            print(f"📡 Wake&Reset: pinging {ping_url}", flush=True)

            try:
                requests.get(ping_url, timeout=5)
            except Exception as e:
                print(f"⏳ Primo ping fallito: {e}", flush=True)

            while elapsed < max_wait_time:
                try:
                    if requests.get(ping_url, timeout=5).status_code == 200:
                        print("✅ Servizio attivo, procedo con set_webhook", flush=True)
                        break
                except:
                    pass
                time.sleep(check_interval)
                elapsed += check_interval

            while True:
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        bot_app.bot.set_webhook(url=WEBHOOK_URL),
                        main_loop
                    )
                    future.result(timeout=10)
                    print("✅ Webhook reimpostato con successo", flush=True)
                    break
                except RetryAfter as e:
                    print(f"⏳ Flood control: riprovo tra {e.retry_after} secondi", flush=True)
                    time.sleep(e.retry_after)
                except Exception as e:
                    print(f"❌ Errore in wake_and_reset thread: {e}", file=sys.stderr, flush=True)
                    break

        except Exception as outer_e:
            print(f"❌ Errore esterno in wake_and_reset: {outer_e}", file=sys.stderr, flush=True)

    threading.Thread(target=background_task).start()
    return "Wake&Reset avviato in background ✅", 200

# --- 13. Avvio del bot ---
async def main():
    print(f"🚀 Imposto webhook: {WEBHOOK_URL}", flush=True)
    await bot_app.bot.set_webhook(url=WEBHOOK_URL)

    await bot_app.bot.set_my_commands([
        BotCommand("vangelo", "Vangelo del giorno")
    ])

    me = await bot_app.bot.get_me()
    print(f"🤖 Username del bot: @{me.username}", flush=True)

    await bot_app.initialize()
    await bot_app.start()
    print("✅ Bot avviato e pronto!", flush=True)

# --- 14. Thread Flask ---
if __name__ == "__main__":
    def start_loop():
        asyncio.set_event_loop(main_loop)
        main_loop.run_until_complete(main())
        main_loop.run_forever()

    threading.Thread(target=start_loop).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

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
from telegram.error import BadRequest
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

# --- 6. Comando /vangelo ---
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

# --- 7. Comando /start ---
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
    except BadRequest as e:
        print(f"⚠️ CallbackQuery scaduta: {e}", flush=True)
        await bot_app.bot.send_message(
            chat_id,
            "⚠️ Il bot si stava riattivando. Per favore clicca di nuovo tra pochi secondi 🙏"
        )
        return

    if query.data == "vangelo_oggi":
        try:
            await query.edit_message_text("📨 Recupero il Vangelo richiesto...")
            await invia_vangelo_oggi(chat_id, TOKEN, None)

            await bot_app.bot.send_message(
                chat_id,
                "Puoi richiedere di nuovo il Vangelo qui sotto 👇",
                reply_markup=get_vangelo_keyboard()
            )

        except Exception as e:
            print(f"❌ Errore nella callback: {e}", file=sys.stderr, flush=True)
            await query.edit_message_text("⚠️ Errore durante l'invio del Vangelo.")

# --- 9. Handlers ---
bot_app.add_handler(CommandHandler("vangelo", vangelo))
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(handle_callback))

# --- 10. Webhook Telegram ---
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

# --- 11. Endpoint /ping per tenere viva l'app ---
@app.route("/ping")
def ping():
    print("🔄 PING ricevuto", flush=True)
    return "✅ Bot attivo", 200

# --- 12. Endpoint /reset_webhook classico ---
@app.route("/reset_webhook")
def reset_webhook():
    print("🔁 Resetting webhook...", flush=True)
    try:
        future = asyncio.run_coroutine_threadsafe(
            bot_app.bot.set_webhook(url=WEBHOOK_URL),
            main_loop
        )
        result = future.result(timeout=10)
        print("✅ Webhook reimpostato correttamente", flush=True)
        return "Webhook reimpostato", 200
    except Exception as e:
        print("❌ Errore nel reset webhook:", e, file=sys.stderr, flush=True)
        return "Errore nel reset webhook", 500

# --- ✅ 13. Nuovo endpoint /wake_and_reset ---
@app.route("/wake_and_reset")
def wake_and_reset():
    print("👋 Wake & Reset INITIATED", flush=True)

    try:
        # 👉 1. Ping del servizio
        ping_url = f"https://{RENDER_HOST}/ping"
        print(f"📡 Pinging self: {ping_url}", flush=True)
        try:
            requests.get(ping_url, timeout=5)
        except Exception as ping_error:
            print(f"⚠️ Errore nel ping: {ping_error}", flush=True)

        # 👉 2. Attesa per avvio completo
        print("⏳ Attesa 120s per risveglio completo...", flush=True)
        time.sleep(120)

        # 👉 3. Reset Webhook
        future = asyncio.run_coroutine_threadsafe(
            bot_app.bot.set_webhook(url=WEBHOOK_URL),
            main_loop
        )
        future.result(timeout=10)

        print("✅ Wake & Webhook reset completati", flush=True)
        return "Wake & Reset COMPLETATO", 200

    except Exception as e:
        print(f"❌ Errore in wake_and_reset: {e}", file=sys.stderr, flush=True)
        return "Errore in wake_and_reset", 500

# --- 14. Avvio bot + Flask ---
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

if __name__ == "__main__":
    def start_loop():
        asyncio.set_event_loop(main_loop)
        main_loop.run_until_complete(main())
        main_loop.run_forever()

    threading.Thread(target=start_loop).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

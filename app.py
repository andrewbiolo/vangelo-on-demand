import os
import sys
import json
import asyncio
import threading
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
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

# --- 4. Comando /vangelo [YYYY-MM-DD] ---
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
    except ValueError as ve:
        await update.message.reply_text(f"⚠️ Errore: {ve}")
    except Exception as e:
        print(f"❌ Errore in /vangelo: {e}", file=sys.stderr, flush=True)
        await update.message.reply_text("⚠️ Errore durante l'invio del Vangelo.")

# --- 5. Inline button con callback ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📖 Vangelo del giorno", callback_data="vangelo_oggi")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Benvenuto! Scegli un'opzione:", reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "vangelo_oggi":
        chat_id = str(query.message.chat.id)
        try:
            await query.edit_message_text("📨 Recupero il Vangelo richiesto...")
            await invia_vangelo_oggi(chat_id, TOKEN, None)
        except Exception as e:
            print(f"❌ Errore nella callback: {e}", file=sys.stderr, flush=True)
            await query.edit_message_text("⚠️ Errore durante l'invio del Vangelo.")

# --- 6. Handlers ---
bot_app.add_handler(CommandHandler("vangelo", vangelo))
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(handle_callback))

# --- 7. Webhook ---
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

# --- 8. Avvio ---
async def main():
    print(f"🚀 Imposto webhook: {WEBHOOK_URL}", flush=True)
    await bot_app.bot.set_webhook(url=WEBHOOK_URL)

    # ✅ Comando /vangelo registrato nel menù
    await bot_app.bot.set_my_commands([
        BotCommand("vangelo", "Vangelo del giorno")
    ])

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

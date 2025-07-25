import os
import sys
import json
import asyncio
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
from datetime import datetime
from vangelo_sender import invia_vangelo_oggi

# --- 1. Configurazione ---
TOKEN = os.getenv("TOKEN")
WEBHOOK_PATH = f"/bot/{TOKEN}"
RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME", "localhost")
WEBHOOK_URL = f"https://{RENDER_HOST}{WEBHOOK_PATH}"

# --- 2. Flask app + bot ---
app = Flask(__name__)
bot_app = Application.builder().token(TOKEN).build()

# --- 3. Tastiera inline ---
def get_vangelo_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Vangelo del giorno", callback_data="vangelo_oggi")]
    ])

# --- 4. Entry point per deep link ---
async def handle_vangelo_entry(chat_id):
    await bot_app.bot.send_message(
        chat_id,
        "Benvenuto! Clicca il bottone per ricevere il Vangelo del giorno 👇",
        reply_markup=get_vangelo_keyboard()
    )

# --- 5. Comando /vangelo ---
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

# --- 6. Comando /start ---
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

# --- 7. Callback inline button ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat.id)

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

# --- 8. Handlers ---
bot_app.add_handler(CommandHandler("vangelo", vangelo))
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(handle_callback))

# --- 9. Webhook Telegram ---
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    try:
        payload = request.get_json(force=True)
        print("📩 JSON ricevuto:\n" + json.dumps(payload, indent=2), flush=True)
        update = Update.de_json(payload, bot_app.bot)
        asyncio.run(bot_app.process_update(update))
        return "OK", 200
    except Exception as e:
        print("❌ Errore nel webhook:", e, file=sys.stderr, flush=True)
        return "Errore interno", 500

# --- ✅ 10. Endpoint /ping per tenere viva l'app ---
@app.route("/ping")
def ping():
    print("🔄 PING ricevuto", flush=True)
    return "✅ Bot attivo", 200

# --- 11. Avvio bot + webhook ---
async def start_bot():
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

# --- 12. Avvio completo ---
if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(start_bot())

    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

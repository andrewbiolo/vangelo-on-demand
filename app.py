
import os
import asyncio
import json
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from vangelo_sender import invia_vangelo_oggi

# --- Config ---
TOKEN = os.getenv("TOKEN")
WEBHOOK_PATH = f"/bot/{TOKEN}"
RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME", "localhost")
WEBHOOK_URL = f"https://{RENDER_HOST}{WEBHOOK_PATH}"

# --- Flask e bot setup ---
app = Flask(__name__)
bot_app = Application.builder().token(TOKEN).build()

# --- Bot handler ---
async def vangelo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = str(update.effective_chat.id)
        await update.message.reply_text("📨 Recupero il Vangelo del giorno, attendi...")
        await invia_vangelo_oggi(chat_id, TOKEN)
    except Exception as e:
        await update.message.reply_text("⚠️ Errore durante l'invio del Vangelo.")
        print(f"❌ Errore nel comando /vangelo: {e}")

bot_app.add_handler(CommandHandler("vangelo", vangelo))

# --- Webhook endpoint ---
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    try:
        print("📍 ENTRATO IN /bot/ webhook")
        payload = request.get_json(force=True)
        print("📩 JSON ricevuto:")
        print(json.dumps(payload, indent=2))

        update = Update.de_json(payload, bot_app.bot)
        bot_app.update_queue.put(update)
        return "OK", 200
    except Exception as e:
        print(f"❌ Errore nel webhook: {e}")
        return "Errore interno", 500

# --- Imposta webhook prima di avviare Flask ---
async def startup():
    await bot_app.bot.set_webhook(url=WEBHOOK_URL)
    print(f"✅ Webhook impostato su {WEBHOOK_URL}")

if __name__ == "__main__":
    print("✅ Avvio setup webhook e Flask...")
    asyncio.run(startup())
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

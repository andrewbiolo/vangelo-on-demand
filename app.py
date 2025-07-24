
import os
import sys
import json
import asyncio
import threading
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime
from vangelo_sender import invia_vangelo_oggi

# --- 1. Loop globale (funziona anche su Render / multithread) ---
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

# --- 4. Handler per il comando /vangelo ---
async def vangelo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📥 Comando /vangelo ricevuto", flush=True)
    chat_id = str(update.effective_chat.id)

    try:
        await update.message.reply_text("📨 Recupero il Vangelo del giorno...")
        await invia_vangelo_oggi(chat_id, TOKEN)
    except Exception as e:
        print(f"❌ Errore in /vangelo: {e}", file=sys.stderr, flush=True)
        await update.message.reply_text("⚠️ Errore durante l'invio del Vangelo.")

bot_app.add_handler(CommandHandler("vangelo", vangelo))

# --- 5. Endpoint Webhook ---
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

# --- 6. Avvio ---
async def main():
    print(f"🚀 Imposto webhook: {WEBHOOK_URL}", flush=True)
    await bot_app.bot.set_webhook(url=WEBHOOK_URL)
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

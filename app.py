import os
import re
import sys
import json
import asyncio
import threading
import feedparser
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime
from bs4 import BeautifulSoup

# --- 1. Loop globale (funziona anche su Render / multithread) ---
main_loop = asyncio.new_event_loop()
asyncio.set_event_loop(main_loop)

# --- 2. Configurazioni ---
TOKEN = os.getenv("TOKEN")
WEBHOOK_PATH = f"/bot/{TOKEN}"
RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME", "localhost")
WEBHOOK_URL = f"https://{RENDER_HOST}{WEBHOOK_PATH}"

ITALIAN_MONTHS = {
    1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile",
    5: "maggio", 6: "giugno", 7: "luglio", 8: "agosto",
    9: "settembre", 10: "ottobre", 11: "novembre", 12: "dicembre"
}

# --- 3. Flask app + bot ---
app = Flask(__name__)
bot_app = Application.builder().token(TOKEN).build()

# --- 4. Funzione parsing del feed RSS ---
def formatta_html(text):
    text = re.sub(r'“([^”]+)”', r'<b>“\1”</b>', text)
    text = re.sub(r'"([^"]+)"', r'<b>"\1"</b>', text)
    text = re.sub(r'«([^»]+)»', r'<i>«\1»</i>', text)
    text = re.sub(r'\(([^)]+)\)', r'<i>(\1)</i>', text)
    text = text.replace("<br>", "").replace("<br/>", "").replace("<br />", "")
    text = re.sub(r'\n+', '\n\n', text.strip())
    return text

def estrai_vangelo(data: datetime.date):
    feed = feedparser.parse("https://www.vaticannews.va/it/vangelo-del-giorno-e-parola-del-giorno.rss.xml")
    giorno = data.day
    mese = ITALIAN_MONTHS[data.month]
    anno = data.year
    data_str = f"{giorno} {mese} {anno}"

    entry = next((e for e in feed.entries if data_str in e.title.lower()), None)
    if not entry:
        return None, None, None, None

    soup = BeautifulSoup(entry.description, "html.parser")
    ps = soup.find_all("p", style="text-align: justify;")
    vangelo, commento = "", ""

    for i, p in enumerate(ps):
        text = p.get_text(separator="\n").strip()
        if text.startswith("Dal Vangelo"):
            vangelo = text
            if i + 1 < len(ps):
                commento = ps[i + 1].get_text(separator="\n").strip()
            break

    righe = vangelo.split('\n')
    if len(righe) > 1:
        titolo = f"<i>{righe[0].strip()}</i>"
        corpo = '\n'.join(righe[1:]).strip()
        vangelo = f"{titolo}\n\n{corpo}"

    return data_str, formatta_html(vangelo), formatta_html(commento), entry.link

# --- 5. Handler per il comando /vangelo ---
async def vangelo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📥 Comando /vangelo ricevuto", flush=True)

    data = datetime.utcnow().date()
    data_str, vangelo_text, commento_text, link = estrai_vangelo(data)

    if not vangelo_text:
        await update.message.reply_text("⚠️ Vangelo non trovato per oggi.")
        return

    await update.message.reply_html(f"📖 <b>Vangelo del giorno ({data_str})</b>\n\n🕊️ {vangelo_text}")
    await update.message.reply_html(f"📝 <b>Commento al Vangelo</b>\n\n{commento_text}")
    await update.message.reply_html(f"🔗 <a href=\"{link}\">Leggi sul sito Vatican News</a>\n\n🌱 Buona giornata!")

bot_app.add_handler(CommandHandler("vangelo", vangelo))

# --- 6. Endpoint Webhook ---
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

# --- 7. Avvio ---
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

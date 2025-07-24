
import os
import re
import argparse
import asyncio
import feedparser
from datetime import datetime
from bs4 import BeautifulSoup
from telegram.ext import Application
from telegram.constants import ParseMode

ITALIAN_MONTHS = {
    1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile",
    5: "maggio", 6: "giugno", 7: "luglio", 8: "agosto",
    9: "settembre", 10: "ottobre", 11: "novembre", 12: "dicembre"
}

def formatta_html(text):
    import re
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
        return data_str, None, None, None

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

async def invia_vangelo_oggi(chat_id: str, token: str):
    application = Application.builder().token(token).build()

    data = datetime.utcnow().date()
    data_str, vangelo, commento, link = estrai_vangelo(data)

    if not vangelo:
        print(f"⚠️ Nessun vangelo trovato per {data_str}")
        return

    await application.bot.send_message(chat_id=chat_id, text=f"📖 <b>Vangelo del giorno ({data_str})</b>\n\n🕊️ {vangelo}", parse_mode=ParseMode.HTML)
    await application.bot.send_message(chat_id=chat_id, text=f"📝 <b>Commento al Vangelo</b>\n\n{commento}", parse_mode=ParseMode.HTML)
    await application.bot.send_message(chat_id=chat_id, text=f"🔗 <a href='{link}'>Leggi sul sito Vatican News</a>\n\n🌱 Buona giornata!", parse_mode=ParseMode.HTML, disable_web_page_preview=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Invia il Vangelo del giorno a una chat Telegram.")
    parser.add_argument("--chat_id", type=str, help="ID della chat Telegram", required=True)
    args = parser.parse_args()

    TOKEN = os.getenv("TOKEN")
    if not TOKEN:
        raise EnvironmentError("Variabile d'ambiente TOKEN non definita")

    asyncio.run(invia_vangelo_oggi(args.chat_id, TOKEN))

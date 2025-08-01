import os
import sys
import asyncio
import feedparser
from telegram import Bot
from datetime import datetime
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
import re

ITALIAN_MONTHS = {
    1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile",
    5: "maggio", 6: "giugno", 7: "luglio", 8: "agosto",
    9: "settembre", 10: "ottobre", 11: "novembre", 12: "dicembre"
}

def formatta_html(text):
    text = re.sub(r'“([^”]+)”', r'<b>“\1”</b>', text)
    text = re.sub(r'"([^"]+)"', r'<b>"\1"</b>', text)
    text = re.sub(r'«([^»]+)»', r'<i>«\1»</i>', text)
    text = re.sub(r'\(([^)]+)\)', r'<i>(\1)</i>', text)
    text = text.replace("<br>", "").replace("<br/>", "").replace("<br />", "")
    text = re.sub(r'\n+', '\n\n', text.strip())
    return text

def carica_feed():
    try:
        print("🌐 Caricamento feed online...")
        feed = feedparser.parse("https://www.vaticannews.va/it/vangelo-del-giorno-e-parola-del-giorno.rss.xml")
        if len(feed.entries) == 0:
            raise Exception("Feed online vuoto")
        return feed
    except Exception as e:
        print(f"⚠️ Errore caricamento feed online: {e}")
        print("📁 Caricamento feed locale da 'vangeldelgiorno.xml'...")
        return feedparser.parse("vangeldelgiorno.xml")

def estrai_vangelo(data: datetime.date):
    feed = carica_feed()
    entry = None

    print(f"\n📅 Cerco pubDate = {data}")

    for e in feed.entries:
        try:
            pub_date = parsedate_to_datetime(e.published).date()
            if pub_date == data:
                print(f"✅ MATCH trovato: {e.title}")
                entry = e
                break
        except Exception as ex:
            print(f"❌ Errore parsing {e.title}: {ex}")

    if not entry:
        print("❌ Nessuna entry con data corrispondente.")
        return None, None, None, None

    soup = BeautifulSoup(entry.description, "html.parser")
    ps = soup.find_all("p")
    print(f"🔎 Trovati {len(ps)} paragrafi nel <description>")

    vangelo, commento = "", ""
    for i in range(len(ps)):
        text = ps[i].get_text(separator="\n").strip()
        print(f"  ▶️ paragrafo {i}: {text[:80]}...")

        if "Dal Vangelo" in text:
            print("📌 Trovato paragrafo con 'Dal Vangelo'")

            # Raccogli tutti i paragrafi non vuoti da questo punto in poi
            blocchi = [p.get_text(separator="\n").strip() for p in ps[i:] if p.get_text(strip=True)]
            print(f"📦 Blocchi non vuoti da 'Dal Vangelo': {len(blocchi)}")

            if len(blocchi) >= 3:
                titolo = blocchi[0]
                corpo = blocchi[1]
                commento = blocchi[2]
                vangelo = f"<i>{titolo}</i>\n\n{corpo}"
                print("📌 Struttura: titolo + corpo + commento")
            elif len(blocchi) == 2:
                titolo_e_corpo = blocchi[0]
                commento = blocchi[1]
                vangelo = f"<i>{titolo_e_corpo}</i>"
                print("📌 Struttura: titolo+corpo uniti, commento separato")
            elif len(blocchi) == 1:
                vangelo = f"<i>{blocchi[0]}</i>"
                commento = ""
                print("📌 Struttura: solo titolo+corpo uniti")
            else:
                vangelo = commento = ""
                print("❌ Nessun contenuto rilevato")

            break

    if not vangelo:
        print("⚠️ Nessun testo con 'Dal Vangelo' trovato nel contenuto.")
        return None, None, None, None

    data_str = f"{data.day} {ITALIAN_MONTHS[data.month]} {data.year}"
    return data_str, formatta_html(vangelo), formatta_html(commento), entry.link

async def invia_vangelo_oggi(chat_id: str, token: str, date_str: str = None):
    if date_str:
        try:
            if "-" in date_str and len(date_str.split("-")[0]) == 2:
                data = datetime.strptime(date_str, "%d-%m-%Y").date()
            else:
                data = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Data non valida. Usa il formato DD-MM-YYYY o YYYY-MM-DD (es: 01-08-2025)")
    else:
        data = datetime.utcnow().date()

    data_str, vangelo_text, commento_text, link = estrai_vangelo(data)
    if not vangelo_text:
        raise ValueError(f"Nessun Vangelo trovato per la data {data.strftime('%d-%m-%Y')}.")

    bot = Bot(token=token)

    await bot.send_message(chat_id=chat_id,
                           text=f"📖 <b>Vangelo del giorno ({data_str})</b>\n\n🕊️ {vangelo_text}",
                           parse_mode='HTML')

    if commento_text:
        await bot.send_message(chat_id=chat_id,
                               text=f"📝 <b>Commento al Vangelo</b>\n\n{commento_text}",
                               parse_mode='HTML')

    await bot.send_message(chat_id=chat_id,
                           text=f"🔗 <a href='{link}'>Leggi sul sito Vatican News</a>\n\n🌱 Buona giornata!",
                           parse_mode='HTML',
                           disable_web_page_preview=True)

# --- Esecuzione da terminale ---
if __name__ == "__main__":
    token = os.getenv("TOKEN")
    chat_id = os.getenv("CHAT_ID")
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None

    if not token or not chat_id:
        print("❌ Errore: assicurati di avere le variabili d'ambiente TOKEN e CHAT_ID impostate.")
        sys.exit(1)

    try:
        asyncio.run(invia_vangelo_oggi(chat_id, token, date_arg))
    except Exception as e:
        print(f"❌ Errore durante l'invio del Vangelo: {e}")

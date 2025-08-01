# vangelo_service.py
import feedparser
import re
from datetime import datetime
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime

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
                entry = e
                break
        except Exception as ex:
            print(f"❌ Errore parsing {e.title}: {ex}")

    if not entry:
        return None, None, None, None

    soup = BeautifulSoup(entry.description, "html.parser")
    ps = soup.find_all("p")

    vangelo, commento = "", ""
    for i in range(len(ps)):
        text = ps[i].get_text(separator="\n").strip()
        if "Dal Vangelo" in text:
            blocchi = [p.get_text(separator="\n").strip() for p in ps[i:] if p.get_text(strip=True)]
            if len(blocchi) >= 3:
                titolo = blocchi[0]
                corpo = blocchi[1]
                commento = blocchi[2]
                vangelo = f"<i>{titolo}</i>\n\n{corpo}"
            elif len(blocchi) == 2:
                vangelo = f"<i>{blocchi[0]}</i>"
                commento = blocchi[1]
            elif len(blocchi) == 1:
                vangelo = f"<i>{blocchi[0]}</i>"
            break

    if not vangelo:
        return None, None, None, None

    data_str = f"{data.day} {ITALIAN_MONTHS[data.month]} {data.year}"
    return data_str, formatta_html(vangelo), formatta_html(commento), entry.link

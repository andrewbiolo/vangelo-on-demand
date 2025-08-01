# vangelo_sender.py
import os
import sys
import asyncio
from datetime import datetime
from telegram import Bot
from vangelo_service import estrai_vangelo

async def invia_vangelo_oggi(chat_id: str, token: str, date_str: str = None, tipo: str = None):
    if date_str:
        try:
            if "-" in date_str and len(date_str.split("-")[0]) == 2:
                data = datetime.strptime(date_str, "%d-%m-%Y").date()
            else:
                data = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Data non valida. Usa il formato DD-MM-YYYY o YYYY-MM-DD")
    else:
        data = datetime.utcnow().date()

    data_str, vangelo_text, commento_text, link = estrai_vangelo(data)
    if not vangelo_text:
        raise ValueError(f"Nessun Vangelo trovato per la data {data.strftime('%d-%m-%Y')}.")

    bot = Bot(token=token)

    # Logica invio selettivo
    if tipo == "vangelo":
        await bot.send_message(chat_id=chat_id,
                               text=f"📖 <b>Vangelo del giorno ({data_str})</b>\n\n🕊️ {vangelo_text}",
                               parse_mode='HTML')

    elif tipo == "commento":
        if commento_text:
            await bot.send_message(chat_id=chat_id,
                                   text=f"📝 <b>Commento al Vangelo ({data_str})</b>\n\n{commento_text}",
                                   parse_mode='HTML')
        else:
            await bot.send_message(chat_id=chat_id,
                                   text=f"📝 Nessun commento disponibile per il {data_str}.")
    else:
        # Tutto come prima
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

if __name__ == "__main__":
    token = os.getenv("TOKEN")
    chat_id = os.getenv("CHAT_ID")
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    tipo_arg = sys.argv[2].lower() if len(sys.argv) > 2 else None  # "vangelo", "commento" o None

    if not token or not chat_id:
        print("❌ Errore: assicurati di avere le variabili d'ambiente TOKEN e CHAT_ID impostate.")
        sys.exit(1)

    try:
        asyncio.run(invia_vangelo_oggi(chat_id, token, date_arg, tipo_arg))
    except Exception as e:
        print(f"❌ Errore durante l'invio del Vangelo: {e}")

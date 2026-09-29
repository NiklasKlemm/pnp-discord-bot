"""
Zentraler Startpunkt.
Startet den Discord Bot UND das Web-Dashboard gemeinsam im selben
asyncio Event-Loop. Dadurch können Dashboard-Routen direkt Bot-Funktionen
aufrufen (z.B. eine Nachricht posten), ohne einen Umweg über HTTP zwischen
zwei getrennten Programmen.

Starten mit:  python main.py
"""

import asyncio
import signal

from bot import bot, TOKEN
from web import app as web_app, WEB_HOST, WEB_PORT


async def main():
    if not TOKEN:
        raise SystemExit("Kein DISCORD_TOKEN gefunden. Hast du die .env Datei angelegt?")

    # Ohne eigene Signal-Behandlung reagiert nur der Webserver auf ein Stopp-Signal
    # (z.B. von systemd) -- der Bot-Teil würde den Prozess dann bis zum harten
    # Timeout/SIGKILL offenhalten. Deshalb hier beide Teile explizit gemeinsam beenden.
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass  # Windows: add_signal_handler gibt's nicht, Ctrl+C funktioniert trotzdem

    async with bot:
        bot_task = asyncio.create_task(bot.start(TOKEN))
        web_task = asyncio.create_task(
            web_app.run_task(host=WEB_HOST, port=WEB_PORT, shutdown_trigger=stop_event.wait)
        )

        await stop_event.wait()
        await bot.close()
        await asyncio.gather(bot_task, web_task, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())

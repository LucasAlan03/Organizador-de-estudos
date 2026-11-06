"""Inicia o site em http://127.0.0.1:8765 e, com token no .env, o bot do Telegram (python -m app)."""
from __future__ import annotations

import os
import threading
from datetime import date, datetime
from pathlib import Path

import uvicorn

from app.backup import backup_db
from app.bot import Bot
from app.db import connect, init_schema
from app.env import load_env
from app.telegram_api import TelegramClient
from app.web import create_app

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "study.db"
BACKUP_DIR = ROOT / "data" / "backups"


def start_bot(root: Path, db_path: Path) -> tuple[threading.Thread, threading.Event] | None:
    """Sobe o bot em uma thread. Sem token no .env, devolve None e o site roda sozinho."""
    token = load_env(root / ".env").get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Bot desligado: sem TELEGRAM_BOT_TOKEN no .env")
        return None
    stop = threading.Event()

    def work() -> None:
        conn = connect(db_path)
        init_schema(conn)
        Bot(conn, TelegramClient(token), datetime.now, str(root)).run(stop)
        conn.close()

    thread = threading.Thread(target=work, name="telegram-bot", daemon=True)
    thread.start()
    print("Bot do Telegram ligado.")
    return thread, stop


def main() -> None:
    backup_db(DB_PATH, BACKUP_DIR, date.today())
    bot = start_bot(ROOT, DB_PATH)
    try:
        uvicorn.run(create_app(DB_PATH), host="127.0.0.1", port=8765)
    finally:
        if bot:
            bot[1].set()


if __name__ == "__main__":
    main()

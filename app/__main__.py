"""Inicia o site em http://127.0.0.1:8000 (python -m app)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import uvicorn

from app.backup import backup_db
from app.web import create_app

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "study.db"
BACKUP_DIR = ROOT / "data" / "backups"


def main() -> None:
    backup_db(DB_PATH, BACKUP_DIR, date.today())
    uvicorn.run(create_app(DB_PATH), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()

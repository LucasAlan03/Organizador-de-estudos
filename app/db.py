"""Acesso ao SQLite: conexão, schema e configurações."""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS topics (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    position INTEGER NOT NULL,
    pdf_title TEXT NOT NULL,
    pdf_pages INTEGER NOT NULL,
    list_title TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK (kind IN ('page', 'exercise')),
    topic_id TEXT NOT NULL REFERENCES topics(id),
    exercise INTEGER,
    sub TEXT,
    page INTEGER,
    label TEXT NOT NULL,
    position INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES items(id),
    minutes REAL NOT NULL,
    day TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_logs_day ON logs(day);
CREATE INDEX IF NOT EXISTS idx_logs_item ON logs(item_id);
CREATE TABLE IF NOT EXISTS days (
    day TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pendente'
        CHECK (status IN ('pendente', 'vai_estudar', 'estudou', 'pulou')),
    last_alert_at TEXT,
    snooze_until TEXT,
    alert_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS weekly_goals (
    week_start TEXT PRIMARY KEY,
    minutes REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""

DEFAULT_SETTINGS = {
    "exam_date": "2026-12-12",
    "daily_goal_min": "90",
    "alert_time": "18:30",
    "snooze_min": "30",
}


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Uma conexão por requisição; o FastAPI pode criar e usar em threads diferentes.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate_days(conn: sqlite3.Connection) -> None:
    """Bancos criados na Fase 1 não têm as colunas do alerta."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(days)")}
    for name, ddl in (
        ("snooze_until", "TEXT"),
        ("alert_count", "INTEGER NOT NULL DEFAULT 0"),
    ):
        if name in cols:
            continue
        try:
            conn.execute(f"ALTER TABLE days ADD COLUMN {name} {ddl}")
        except sqlite3.OperationalError as exc:
            if "duplicate column" not in str(exc):  # outra conexão migrou primeiro
                raise


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _migrate_days(conn)
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value)
        )
    conn.commit()


def get_setting(conn: sqlite3.Connection, key: str) -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        raise KeyError(key)
    return row["value"]


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def ensure_start_date(conn: sqlite3.Connection, today: date) -> date:
    row = conn.execute("SELECT value FROM settings WHERE key = 'start_date'").fetchone()
    if row is not None:
        return date.fromisoformat(row["value"])
    set_setting(conn, "start_date", today.isoformat())
    return today

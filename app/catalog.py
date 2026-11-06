"""Carrega o catálogo (assuntos, páginas de teoria, exercícios) no banco."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DEFAULT_CATALOG = Path(__file__).resolve().parent.parent / "catalog" / "catalog.json"


def load_catalog(conn: sqlite3.Connection, path: Path = DEFAULT_CATALOG) -> None:
    """Insere/atualiza o catálogo. Idempotente: nunca duplica itens."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for topic in data["topics"]:
        tid = topic["id"]
        conn.execute(
            "INSERT INTO topics(id, title, position, pdf_title, pdf_pages, list_title) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
            "title=excluded.title, position=excluded.position, "
            "pdf_title=excluded.pdf_title, pdf_pages=excluded.pdf_pages, "
            "list_title=excluded.list_title",
            (tid, topic["title"], topic["position"], topic["pdf"]["title"],
             topic["pdf"]["pages"], topic["list"]["title"]),
        )
        for page in range(1, topic["pdf"]["pages"] + 1):
            _upsert_item(conn, f"{tid}:p{page}", "page", tid, None, None, page,
                         f"Página {page}", page)
        position = 0
        for ex in topic["list"]["exercises"]:
            n, subs = ex["n"], ex["subs"]
            if not subs:
                position += 1
                _upsert_item(conn, f"{tid}:e{n}", "exercise", tid, n, None, None,
                             f"Exercício {n}", position)
            for sub in subs:
                position += 1
                _upsert_item(conn, f"{tid}:e{n}:{sub}", "exercise", tid, n, sub, None,
                             f"Exercício {n} ({sub})", position)
    conn.commit()


def _upsert_item(conn, key, kind, topic_id, exercise, sub, page, label, position):
    conn.execute(
        "INSERT INTO items(key, kind, topic_id, exercise, sub, page, label, position) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET "
        "label=excluded.label, position=excluded.position",
        (key, kind, topic_id, exercise, sub, page, label, position),
    )

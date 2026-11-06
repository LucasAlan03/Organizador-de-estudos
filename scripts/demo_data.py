"""Cria um banco de demonstração com ~3 semanas de estudo fictício.

Uso:  python scripts/demo_data.py [caminho.db] [AAAA-MM-DD hoje]
Serve para prints, GIFs e a vitrine online; não toca em data/study.db.
"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402
from app.catalog import load_catalog  # noqa: E402
from app.logs import recompute_day_status  # noqa: E402


def build(path: Path, today: date) -> None:
    if path.exists():
        path.unlink()
    conn = db.connect(path)
    db.init_schema(conn)
    load_catalog(conn)
    start = today - timedelta(days=21)
    db.set_setting(conn, "start_date", start.isoformat())

    rng = random.Random(42)
    topics = [r["id"] for r in conn.execute("SELECT id FROM topics ORDER BY position")]
    # Teoria: primeiros assuntos bem adiantados, os últimos ainda no começo.
    page_share = [1.0, 0.85, 0.6, 0.3, 0.1, 0.0]
    # Exercícios: um pouco atrás da teoria.
    ex_share = [0.9, 0.6, 0.35, 0.1, 0.0, 0.0]
    # Assuntos mais difíceis levam mais tempo por item (gera a lista de reforço).
    hardness = [1.0, 0.9, 1.6, 1.2, 1.0, 1.0]

    queue = []
    for i, t in enumerate(topics):
        pages = conn.execute(
            "SELECT id FROM items WHERE topic_id=? AND kind='page' ORDER BY page", (t,)
        ).fetchall()
        exs = conn.execute(
            "SELECT id FROM items WHERE topic_id=? AND kind='exercise' ORDER BY position", (t,)
        ).fetchall()
        for r in pages[: int(len(pages) * page_share[i % 6])]:
            queue.append((r["id"], rng.uniform(9, 16) * hardness[i % 6]))
        for r in exs[: int(len(exs) * ex_share[i % 6])]:
            queue.append((r["id"], rng.uniform(15, 30) * hardness[i % 6]))

    # Distribui os itens pelos dias de estudo (~3 a 4 por semana, ~1h30 cada).
    study_days = [start + timedelta(days=d) for d in range(22) if rng.random() < 0.6]
    if today not in study_days:
        study_days.append(today)
    for k, (item_id, minutes) in enumerate(queue):
        day = study_days[k * len(study_days) // len(queue)]
        conn.execute(
            "INSERT INTO logs(item_id, minutes, day) VALUES (?,?,?)",
            (item_id, round(minutes, 1), day.isoformat()),
        )
    for day in study_days:
        recompute_day_status(conn, day)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "demo.db"
    today = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
    build(out, today)
    print(f"Banco de demonstração criado em {out}")

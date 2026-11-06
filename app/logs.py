"""Registro de tempo de estudo por item, com validação e status do dia."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

MAX_MINUTES = 600


class LogError(ValueError):
    """Erro de validação com mensagem pronta para mostrar ao usuário."""


@dataclass(frozen=True)
class AddResult:
    log_id: int
    item_id: int
    is_review: bool


def parse_minutes(raw: str) -> float:
    text = (raw or "").strip().replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        raise LogError(f"Informe os minutos (de 1 a {MAX_MINUTES}).") from None
    if not 0 < value <= MAX_MINUTES:
        raise LogError(f"Os minutos devem ficar entre 1 e {MAX_MINUTES}.")
    return value


def _check_minutes(minutes: float) -> None:
    if not 0 < minutes <= MAX_MINUTES:
        raise LogError(f"Os minutos devem ficar entre 1 e {MAX_MINUTES}.")


def _check_day(day: date, today: date) -> None:
    if day > today:
        raise LogError("A data não pode estar no futuro.")


def recompute_day_status(conn: sqlite3.Connection, day: date) -> None:
    iso = day.isoformat()
    has_logs = conn.execute("SELECT 1 FROM logs WHERE day = ? LIMIT 1", (iso,)).fetchone()
    row = conn.execute("SELECT status FROM days WHERE day = ?", (iso,)).fetchone()
    if has_logs:
        conn.execute(
            "INSERT INTO days(day, status) VALUES (?, 'estudou') "
            "ON CONFLICT(day) DO UPDATE SET status = 'estudou'",
            (iso,),
        )
    elif row is not None and row["status"] == "estudou":
        conn.execute("UPDATE days SET status = 'pendente' WHERE day = ?", (iso,))


def _insert(conn: sqlite3.Connection, item_id: int, minutes: float, day: date) -> AddResult:
    if conn.execute("SELECT 1 FROM items WHERE id = ?", (item_id,)).fetchone() is None:
        raise LogError("Item não encontrado.")
    review = conn.execute(
        "SELECT 1 FROM logs WHERE item_id = ? LIMIT 1", (item_id,)
    ).fetchone() is not None
    cur = conn.execute(
        "INSERT INTO logs(item_id, minutes, day) VALUES (?, ?, ?)",
        (item_id, minutes, day.isoformat()),
    )
    return AddResult(log_id=cur.lastrowid, item_id=item_id, is_review=review)


def add_item_log(
    conn: sqlite3.Connection, item_id: int, minutes: float, day: date, today: date
) -> AddResult:
    _check_minutes(minutes)
    _check_day(day, today)
    result = _insert(conn, item_id, minutes, day)
    recompute_day_status(conn, day)
    conn.commit()
    return result


def add_page_range_log(
    conn: sqlite3.Connection, topic_id: str, page_from: int, page_to: int,
    minutes: float, day: date, today: date,
) -> list[AddResult]:
    """Registra um intervalo de páginas; o tempo total é dividido igualmente."""
    _check_minutes(minutes)
    _check_day(day, today)
    topic = conn.execute(
        "SELECT pdf_pages FROM topics WHERE id = ?", (topic_id,)
    ).fetchone()
    if topic is None:
        raise LogError("Assunto não encontrado.")
    pages = topic["pdf_pages"]
    if page_from > page_to:
        raise LogError("A página inicial não pode ser maior que a final.")
    if page_from < 1 or page_to > pages:
        raise LogError(f"As páginas devem ir de 1 a {pages}.")
    count = page_to - page_from + 1
    each = minutes / count
    results: list[AddResult] = []
    try:
        for page in range(page_from, page_to + 1):
            row = conn.execute(
                "SELECT id FROM items WHERE topic_id = ? AND kind = 'page' AND page = ?",
                (topic_id, page),
            ).fetchone()
            results.append(_insert(conn, row["id"], each, day))
        recompute_day_status(conn, day)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return results


def update_log(
    conn: sqlite3.Connection, log_id: int, minutes: float, day: date, today: date
) -> None:
    _check_minutes(minutes)
    _check_day(day, today)
    row = conn.execute("SELECT day FROM logs WHERE id = ?", (log_id,)).fetchone()
    if row is None:
        raise LogError("Registro não encontrado.")
    old_day = date.fromisoformat(row["day"])
    conn.execute(
        "UPDATE logs SET minutes = ?, day = ? WHERE id = ?",
        (minutes, day.isoformat(), log_id),
    )
    recompute_day_status(conn, old_day)
    recompute_day_status(conn, day)
    conn.commit()


def delete_log(conn: sqlite3.Connection, log_id: int) -> None:
    row = conn.execute("SELECT day FROM logs WHERE id = ?", (log_id,)).fetchone()
    if row is None:
        raise LogError("Registro não encontrado.")
    conn.execute("DELETE FROM logs WHERE id = ?", (log_id,))
    recompute_day_status(conn, date.fromisoformat(row["day"]))
    conn.commit()


def add_many_item_logs(
    conn: sqlite3.Connection, entries: list[tuple[int, float]], day: date, today: date
) -> list[AddResult]:
    """Registra vários itens de uma vez (tudo-ou-nada). `entries` = [(item_id, minutos)]."""
    if not entries:
        raise LogError("Marque ao menos um item.")
    _check_day(day, today)
    for _, minutes in entries:
        _check_minutes(minutes)
    results: list[AddResult] = []
    try:
        for item_id, minutes in entries:
            results.append(_insert(conn, item_id, minutes, day))
        recompute_day_status(conn, day)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return results

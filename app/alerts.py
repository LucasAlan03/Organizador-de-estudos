"""Regras do alerta diário: quando avisar e o que cada botão faz (sem rede)."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, time, timedelta

CUTOFF = time(22, 0)  # depois disso não há mais alertas no dia


def should_alert(
    status: str,
    now: datetime,
    alert_time: time,
    snooze_until: datetime | None,
    last_alert_at: datetime | None,
) -> bool:
    """Decide se o alerta deve sair agora. Cobre horário normal, adiamento e catch-up."""
    if status != "pendente":
        return False
    if now.time() >= CUTOFF or now.time() < alert_time:
        return False
    if snooze_until is not None:
        return now >= snooze_until
    return last_alert_at is None or last_alert_at.date() != now.date()


def get_day(conn: sqlite3.Connection, day: date) -> sqlite3.Row:
    conn.execute("INSERT OR IGNORE INTO days(day) VALUES (?)", (day.isoformat(),))
    conn.commit()
    return conn.execute("SELECT * FROM days WHERE day = ?", (day.isoformat(),)).fetchone()


def mark_alert_sent(conn: sqlite3.Connection, now: datetime) -> None:
    get_day(conn, now.date())
    conn.execute(
        "UPDATE days SET last_alert_at = ?, alert_count = alert_count + 1, "
        "snooze_until = NULL WHERE day = ?",
        (now.isoformat(), now.date().isoformat()),
    )
    conn.commit()


def apply_action(conn: sqlite3.Connection, action: str, now: datetime, snooze_min: int) -> str:
    """Aplica o botão apertado e devolve o texto de resposta."""
    day = now.date().isoformat()
    row = get_day(conn, now.date())
    if row["status"] == "estudou":
        return "Você já estudou hoje. Bom trabalho!"
    if action == "agora":
        conn.execute("UPDATE days SET status = 'vai_estudar', snooze_until = NULL WHERE day = ?", (day,))
        text = "Boa! Abra o site e registre o tempo quando terminar."
    elif action == "hoje_nao":
        conn.execute("UPDATE days SET status = 'pulou', snooze_until = NULL WHERE day = ?", (day,))
        text = "Tudo bem, hoje fica de fora. Amanhã eu aviso de novo."
    elif action == "adiar":
        until = now + timedelta(minutes=snooze_min)
        conn.execute("UPDATE days SET snooze_until = ? WHERE day = ?", (until.isoformat(), day))
        text = f"Combinado, aviso de novo em {snooze_min} min."
    else:
        return "Não entendi esse botão."
    conn.commit()
    return text

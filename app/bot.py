"""Bot do Telegram: envia o alerta diário e trata os botões. Roda ao lado do site."""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, time
from typing import Callable

from app.alerts import apply_action, get_day, mark_alert_sent, should_alert
from app.db import get_setting, set_setting
from app.telegram_api import TelegramError

SITE_URL = "http://127.0.0.1:8765"
BACKOFF_START = 5
BACKOFF_MAX = 300
POLL_TIMEOUT = 25


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class Bot:
    def __init__(
        self,
        conn: sqlite3.Connection,
        client,
        now: Callable[[], datetime],
        project_path: str,
        sleep: Callable[[float], object] | None = None,
    ) -> None:
        self.conn = conn
        self.client = client
        self.now = now
        self.project_path = project_path
        self._sleep = sleep

    # -- estado -----------------------------------------------------------
    def _chat_id(self) -> int | None:
        try:
            return int(get_setting(self.conn, "telegram_chat_id"))
        except (KeyError, ValueError):
            return None

    def _minutes_today(self, day_iso: str) -> float:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(minutes), 0) AS m FROM logs WHERE day = ?", (day_iso,)
        ).fetchone()
        return row["m"]

    def _footer(self) -> str:
        return f"Pasta: {self.project_path}"

    # -- alerta -----------------------------------------------------------
    def tick(self) -> bool:
        chat = self._chat_id()
        if chat is None:
            return False
        now = self.now()
        row = get_day(self.conn, now.date())
        alert_time = time.fromisoformat(get_setting(self.conn, "alert_time"))
        if not should_alert(
            row["status"],
            now,
            alert_time,
            _parse_dt(row["snooze_until"]),
            _parse_dt(row["last_alert_at"]),
        ):
            return False
        snooze = int(get_setting(self.conn, "snooze_min"))
        goal = int(float(get_setting(self.conn, "daily_goal_min")))
        done = round(self._minutes_today(now.date().isoformat()))
        text = f"Hora de estudar? Hoje: {done} de {goal} min.\n{self._footer()}"
        buttons = [[("Consigo agora", "agora"), (f"Daqui {snooze} min", "adiar"), ("Hoje não", "hoje_nao")]]
        try:
            self.client.send_message(chat, text, buttons)
        except TelegramError:
            return False
        mark_alert_sent(self.conn, now)
        return True

    # -- mensagens e botões -------------------------------------------------
    def handle_update(self, update: dict) -> None:
        try:
            if "message" in update:
                self._handle_message(update["message"])
            elif "callback_query" in update:
                self._handle_callback(update["callback_query"])
        except TelegramError:
            pass  # a resposta falhou; o estado já foi gravado

    def _handle_message(self, message: dict) -> None:
        chat = message["chat"]["id"]
        if (message.get("text") or "").strip().split("@")[0] != "/start":
            return
        bound = self._chat_id()
        if bound is None:
            set_setting(self.conn, "telegram_chat_id", str(chat))
            self.client.send_message(chat, f"Conectado! Vou avisar aqui na hora de estudar.\n{self._footer()}")
        elif bound == chat:
            self.client.send_message(chat, "Já estou conectado a este chat.")

    def _handle_callback(self, cb: dict) -> None:
        chat = cb["message"]["chat"]["id"]
        if chat != self._chat_id():
            return
        action = cb.get("data", "")
        snooze = int(get_setting(self.conn, "snooze_min"))
        text = apply_action(self.conn, action, self.now(), snooze)
        if action == "agora" and get_day(self.conn, self.now().date())["status"] == "vai_estudar":
            text = f"{text}\n{SITE_URL}\n{self._footer()}"
        self.client.answer_callback(cb["id"])
        self.client.edit_message(chat, cb["message"]["message_id"], text)

    # -- laço principal -----------------------------------------------------
    def run(self, stop: threading.Event) -> None:
        offset: int | None = None
        wait = 0
        sleep = self._sleep or stop.wait
        while not stop.is_set():
            try:
                self.tick()
                for update in self.client.get_updates(offset, timeout=POLL_TIMEOUT):
                    offset = update["update_id"] + 1
                    self.handle_update(update)
                wait = 0
            except (TelegramError, sqlite3.Error):  # o site segue de pé; tenta de novo
                wait = BACKOFF_START if wait == 0 else min(wait * 2, BACKOFF_MAX)
                sleep(wait)

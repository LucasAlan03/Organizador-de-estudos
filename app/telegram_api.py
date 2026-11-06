"""Cliente fino da API de bots do Telegram, sobre httpx."""
from __future__ import annotations

import httpx

API = "https://api.telegram.org"


class TelegramError(RuntimeError):
    """Falha ao falar com o Telegram. A mensagem nunca contém o token."""


class TelegramClient:
    def __init__(self, token: str, http: httpx.Client | None = None) -> None:
        self._token = token
        # o timeout do cliente precisa ser maior que o do long polling
        self._http = http or httpx.Client(timeout=40)

    def _call(self, method: str, payload: dict):
        try:
            resp = self._http.post(f"{API}/bot{self._token}/{method}", json=payload)
        except httpx.HTTPError as exc:
            raise TelegramError(f"Falha de rede em {method} ({type(exc).__name__}).") from None
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if resp.status_code != 200 or not data.get("ok"):
            detail = data.get("description", "")
            raise TelegramError(f"Telegram recusou {method} (HTTP {resp.status_code}) {detail}".strip())
        return data["result"]

    def get_updates(self, offset: int | None, timeout: int = 25) -> list[dict]:
        payload: dict = {"timeout": timeout, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            payload["offset"] = offset
        return self._call("getUpdates", payload)

    def send_message(
        self, chat_id: int, text: str, buttons: list[list[tuple[str, str]]] | None = None
    ) -> int:
        payload: dict = {"chat_id": chat_id, "text": text}
        if buttons:
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [{"text": label, "callback_data": data} for label, data in row]
                    for row in buttons
                ]
            }
        return self._call("sendMessage", payload)["message_id"]

    def answer_callback(self, callback_id: str, text: str = "") -> None:
        self._call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})

    def edit_message(self, chat_id: int, message_id: int, text: str) -> None:
        self._call(
            "editMessageText",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "reply_markup": {"inline_keyboard": []},
            },
        )

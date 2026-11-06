import json

import httpx
import pytest

from app.telegram_api import TelegramClient, TelegramError

TOKEN = "123:SECRET"


def make(handler):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return TelegramClient(TOKEN, http=http)


def ok(result):
    return httpx.Response(200, json={"ok": True, "result": result})


def test_send_message_posts_text_and_inline_keyboard():
    seen = {}

    def handler(req):
        seen["path"] = req.url.path
        seen["body"] = json.loads(req.content)
        return ok({"message_id": 77})

    mid = make(handler).send_message(5, "oi", [[("Sim", "a"), ("Não", "b")]])
    assert mid == 77
    assert seen["path"] == f"/bot{TOKEN}/sendMessage"
    assert seen["body"]["chat_id"] == 5
    assert seen["body"]["text"] == "oi"
    assert seen["body"]["reply_markup"]["inline_keyboard"] == [
        [{"text": "Sim", "callback_data": "a"}, {"text": "Não", "callback_data": "b"}]
    ]


def test_get_updates_passes_offset_and_timeout():
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        return ok([{"update_id": 1}])

    assert make(handler).get_updates(10, timeout=7) == [{"update_id": 1}]
    assert seen["body"]["offset"] == 10
    assert seen["body"]["timeout"] == 7


def test_ok_false_raises_telegram_error():
    def handler(req):
        return httpx.Response(200, json={"ok": False, "description": "Bad Request"})

    with pytest.raises(TelegramError):
        make(handler).answer_callback("x")


def test_network_error_raises_without_token_in_message():
    def handler(req):
        raise httpx.ConnectError(f"falhou {req.url}")

    with pytest.raises(TelegramError) as exc:
        make(handler).send_message(1, "x")
    assert "SECRET" not in str(exc.value)


def test_http_error_status_raises_without_token():
    def handler(req):
        return httpx.Response(401, text="unauthorized")

    with pytest.raises(TelegramError) as exc:
        make(handler).get_updates(None)
    assert "SECRET" not in str(exc.value)


def test_edit_message_removes_keyboard():
    seen = {}

    def handler(req):
        seen["path"] = req.url.path
        seen["body"] = json.loads(req.content)
        return ok(True)

    make(handler).edit_message(5, 9, "feito")
    assert seen["path"].endswith("/editMessageText")
    assert seen["body"]["message_id"] == 9
    assert seen["body"]["reply_markup"] == {"inline_keyboard": []}

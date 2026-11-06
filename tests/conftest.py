import pytest

from app.db import connect, init_schema


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "test.db")
    init_schema(c)
    yield c
    c.close()


@pytest.fixture
def catconn(conn):
    """Banco com o catálogo real carregado."""
    from app.catalog import DEFAULT_CATALOG, load_catalog

    load_catalog(conn, DEFAULT_CATALOG)
    return conn


def item_id(conn, key):
    return conn.execute("SELECT id FROM items WHERE key = ?", (key,)).fetchone()["id"]


@pytest.fixture
def client(tmp_path):
    from datetime import date

    from fastapi.testclient import TestClient

    from app.web import create_app

    app = create_app(tmp_path / "web.db", today=lambda: date(2026, 11, 6))
    return TestClient(app)


def open_db(client):
    """Conexão direta ao banco usado pelo app de teste."""
    return connect(client.app.state.db_path)


class FakeTelegram:
    """Cliente Telegram falso: registra chamadas e entrega updates programados."""

    def __init__(self):
        self.sent = []  # dicts: chat_id, text, buttons, message_id
        self.answered = []
        self.edited = []
        self.updates = []
        self.get_updates_calls = 0
        self.fail_send = False
        self.fail_get_updates = 0  # quantas chamadas a get_updates devem falhar
        self.on_get_updates = None

    def get_updates(self, offset, timeout=25):
        from app.telegram_api import TelegramError

        self.get_updates_calls += 1
        if self.on_get_updates:
            self.on_get_updates(self.get_updates_calls)
        if self.fail_get_updates > 0:
            self.fail_get_updates -= 1
            raise TelegramError("fora do ar")
        out, self.updates = self.updates, []
        return out

    def send_message(self, chat_id, text, buttons=None):
        from app.telegram_api import TelegramError

        if self.fail_send:
            raise TelegramError("fora do ar")
        mid = len(self.sent) + 100
        self.sent.append({"chat_id": chat_id, "text": text, "buttons": buttons, "message_id": mid})
        return mid

    def answer_callback(self, callback_id, text=""):
        self.answered.append(callback_id)

    def edit_message(self, chat_id, message_id, text):
        self.edited.append({"chat_id": chat_id, "message_id": message_id, "text": text})


@pytest.fixture
def tg():
    return FakeTelegram()

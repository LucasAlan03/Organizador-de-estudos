import time

import app.__main__ as main_mod


class QuietClient:
    def __init__(self, token):
        self.token = token

    def get_updates(self, offset, timeout=25):
        time.sleep(0.01)
        return []


def test_start_bot_returns_none_without_token(tmp_path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    (tmp_path / ".env").write_text("", encoding="utf-8")
    assert main_mod.start_bot(tmp_path, tmp_path / "d.db") is None


def test_start_bot_returns_thread_with_token(tmp_path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    (tmp_path / ".env").write_text("TELEGRAM_BOT_TOKEN=1:abc\n", encoding="utf-8")
    monkeypatch.setattr(main_mod, "TelegramClient", QuietClient)
    thread, stop = main_mod.start_bot(tmp_path, tmp_path / "d.db")
    assert thread.is_alive()
    stop.set()
    thread.join(timeout=2)
    assert not thread.is_alive()

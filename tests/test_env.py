from app.env import load_env


def test_load_env_parses_values_quotes_comments(tmp_path):
    f = tmp_path / ".env"
    f.write_text('# comentário\n\nA=1\nB="dois"\nC = \'tres\'\nSEM_IGUAL\n', encoding="utf-8")
    assert load_env(f) == {"A": "1", "B": "dois", "C": "tres"}


def test_load_env_missing_file_returns_empty(tmp_path):
    assert load_env(tmp_path / "nao-existe") == {}


def test_load_env_accepts_utf8_bom(tmp_path):
    f = tmp_path / ".env"
    f.write_bytes(b"\xef\xbb\xbfTELEGRAM_BOT_TOKEN=1:abc\n")
    assert load_env(f) == {"TELEGRAM_BOT_TOKEN": "1:abc"}


def test_load_env_accepts_utf16(tmp_path):
    f = tmp_path / ".env"
    f.write_text("TELEGRAM_BOT_TOKEN=1:abc\r\n", encoding="utf-16")
    assert load_env(f) == {"TELEGRAM_BOT_TOKEN": "1:abc"}

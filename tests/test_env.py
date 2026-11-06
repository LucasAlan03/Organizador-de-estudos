from app.env import load_env


def test_load_env_parses_values_quotes_comments(tmp_path):
    f = tmp_path / ".env"
    f.write_text('# comentário\n\nA=1\nB="dois"\nC = \'tres\'\nSEM_IGUAL\n', encoding="utf-8")
    assert load_env(f) == {"A": "1", "B": "dois", "C": "tres"}


def test_load_env_missing_file_returns_empty(tmp_path):
    assert load_env(tmp_path / "nao-existe") == {}

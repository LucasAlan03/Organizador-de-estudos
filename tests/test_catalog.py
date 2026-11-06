import pytest

from app.catalog import DEFAULT_CATALOG, load_catalog


@pytest.fixture
def cat(conn):
    load_catalog(conn, DEFAULT_CATALOG)
    return conn


def count(conn, sql, *args):
    return conn.execute(sql, args).fetchone()[0]


def test_counts(cat):
    ids = [r["id"] for r in cat.execute("SELECT id FROM topics ORDER BY position")]
    assert ids == [
        "fourier", "pares-impares", "conducao-calor",
        "equacao-calor", "onda", "laplace",
    ]
    assert count(cat, "SELECT COUNT(*) FROM items WHERE kind='page'") == 41
    assert count(cat, "SELECT COUNT(*) FROM items WHERE kind='exercise'") == 111
    assert count(
        cat,
        "SELECT COUNT(*) FROM items WHERE topic_id='fourier' AND kind='exercise'",
    ) == 25


def test_labels(cat):
    row = cat.execute("SELECT label FROM items WHERE key='fourier:e4:c'").fetchone()
    assert row["label"] == "Exercício 4 (c)"
    row = cat.execute("SELECT label FROM items WHERE key='fourier:e6'").fetchone()
    assert row["label"] == "Exercício 6"
    assert count(cat, "SELECT COUNT(*) FROM items WHERE key='equacao-calor:e6:c2'") == 1
    row = cat.execute("SELECT label FROM items WHERE key='fourier:p3'").fetchone()
    assert row["label"] == "Página 3"


def test_idempotent(cat):
    load_catalog(cat, DEFAULT_CATALOG)
    assert count(cat, "SELECT COUNT(*) FROM items") == 152
    assert count(cat, "SELECT COUNT(*) FROM topics") == 6

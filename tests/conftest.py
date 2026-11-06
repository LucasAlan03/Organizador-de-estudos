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

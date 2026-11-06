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

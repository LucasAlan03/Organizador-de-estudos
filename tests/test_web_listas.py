from tests.conftest import item_id, open_db


def ids(client, *keys):
    with open_db(client) as c:
        return [item_id(c, k) for k in keys]


def n_logs(client):
    with open_db(client) as c:
        return c.execute("SELECT COUNT(*) FROM logs").fetchone()[0]


def post(client, data):
    return client.post("/listas/fourier/registrar", data=data, follow_redirects=False)


def test_listas_list(client):
    html = client.get("/listas").text
    assert "Lista — Séries de Fourier" in html
    assert "0/25" in html


def test_detail_shows_subitems(client):
    html = client.get("/listas/fourier").text
    assert "Exercício 4" in html
    assert "(c)" in html
    assert "0/25" in html


def test_registrar_subitems(client):
    a, b = ids(client, "fourier:e4:c", "fourier:e6")
    r = post(client, {"day": "2026-11-06", f"item_{a}": "on", f"min_{a}": "20",
                      f"item_{b}": "on", f"min_{b}": "35"})
    assert r.status_code == 303
    assert "ok=" in r.headers["location"]
    assert "2/25" in client.get("/listas/fourier").text
    assert n_logs(client) == 2


def test_all_or_nothing(client):
    a, b = ids(client, "fourier:e4:c", "fourier:e6")
    r = post(client, {"day": "2026-11-06", f"item_{a}": "on", f"min_{a}": "20",
                      f"item_{b}": "on", f"min_{b}": "abc"})
    assert r.status_code == 303
    assert "erro=" in r.headers["location"]
    assert n_logs(client) == 0


def test_unchecked_items_are_ignored(client):
    a, b = ids(client, "fourier:e4:c", "fourier:e6")
    r = post(client, {"day": "2026-11-06", f"item_{a}": "on", f"min_{a}": "20",
                      f"min_{b}": "999"})
    assert "ok=" in r.headers["location"]
    assert n_logs(client) == 1


def test_nothing_checked(client):
    from urllib.parse import unquote_plus
    r = post(client, {"day": "2026-11-06"})
    assert "Marque ao menos um item" in unquote_plus(r.headers["location"])


def test_item_of_other_topic_is_rejected(client):
    (other,) = ids(client, "onda:e1:a")
    r = post(client, {"day": "2026-11-06", f"item_{other}": "on", f"min_{other}": "10"})
    assert "erro=" in r.headers["location"]
    assert n_logs(client) == 0


def test_bad_day(client):
    (a,) = ids(client, "fourier:e6")
    r = post(client, {"day": "2026-11-07", f"item_{a}": "on", f"min_{a}": "10"})
    assert "erro=" in r.headers["location"]
    assert n_logs(client) == 0


def test_unknown_topic_404(client):
    assert client.get("/listas/xyz").status_code == 404
    assert client.post("/listas/xyz/registrar", data={}, follow_redirects=False).status_code == 404

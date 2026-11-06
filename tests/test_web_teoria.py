from urllib.parse import unquote_plus

from tests.conftest import open_db

OK = {"page_from": "1", "page_to": "3", "minutes": "45", "day": "2026-11-06"}


def n_logs(client):
    with open_db(client) as c:
        return c.execute("SELECT COUNT(*) FROM logs").fetchone()[0]


def post(client, **over):
    return client.post("/teoria/fourier/registrar", data={**OK, **over}, follow_redirects=False)


def test_teoria_list(client):
    html = client.get("/teoria").text
    assert "Teoria — Séries de Fourier" in html
    assert "0/7" in html


def test_registrar_pages(client):
    r = post(client)
    assert r.status_code == 303
    assert "ok=" in r.headers["location"]
    html = client.get("/teoria/fourier").text
    assert "3/7" in html
    assert 'class="pg done"' in html
    assert n_logs(client) == 3


def test_registrar_rejects_bad_input(client):
    for over in ({"page_from": "4", "page_to": "2"}, {"minutes": "abc"},
                 {"page_to": "9"}, {"page_from": "x"}, {"day": "2026-11-07"},
                 {"day": "lixo"}, {"minutes": ""}):
        r = post(client, **over)
        assert r.status_code == 303, over
        assert "erro=" in r.headers["location"], over
    assert n_logs(client) == 0


def test_comma_minutes_accepted(client):
    r = post(client, page_from="1", page_to="1", minutes="1,5")
    assert "ok=" in r.headers["location"]
    assert n_logs(client) == 1


def test_review_notice(client):
    post(client, page_from="1", page_to="1")
    r = post(client, page_from="1", page_to="1")
    assert "revisão" in unquote_plus(r.headers["location"])


def test_unknown_topic_404(client):
    assert client.get("/teoria/xyz").status_code == 404
    r = client.post("/teoria/xyz/registrar", data=OK, follow_redirects=False)
    assert r.status_code == 404

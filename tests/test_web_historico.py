from tests.conftest import open_db


def n_logs(client):
    with open_db(client) as c:
        return c.execute("SELECT COUNT(*) FROM logs").fetchone()[0]


def log_one_page(client, page, minutes, day="2026-11-06"):
    return client.post(
        "/teoria/fourier/registrar",
        data={"page_from": str(page), "page_to": str(page), "minutes": str(minutes), "day": day},
        follow_redirects=False,
    )


def first_log_id(client):
    with open_db(client) as c:
        return c.execute("SELECT id FROM logs ORDER BY id LIMIT 1").fetchone()["id"]


def day_status(client, day="2026-11-06"):
    with open_db(client) as c:
        row = c.execute("SELECT status FROM days WHERE day = ?", (day,)).fetchone()
        return row["status"] if row else None


def test_historico_empty(client):
    r = client.get("/historico")
    assert r.status_code == 200
    assert "Nenhum registro" in r.text


def test_registros_listed_with_labels(client):
    log_one_page(client, 2, 30)
    html = client.get("/historico").text
    assert "Página 2" in html
    assert "Séries de Fourier" in html
    assert "2026-11-06" in html or "06/11/2026" in html


def test_delete_log_reverts_day(client):
    log_one_page(client, 1, 30)
    assert day_status(client) == "estudou"
    r = client.post(f"/historico/{first_log_id(client)}/apagar", follow_redirects=False)
    assert r.status_code == 303 and "ok=" in r.headers["location"]
    assert n_logs(client) == 0
    assert day_status(client) == "pendente"


def test_edit_log(client):
    log_one_page(client, 1, 30)
    lid = first_log_id(client)
    r = client.post(f"/historico/{lid}/editar", data={"minutes": "45", "day": "2026-11-06"},
                    follow_redirects=False)
    assert "ok=" in r.headers["location"]
    with open_db(client) as c:
        assert c.execute("SELECT minutes FROM logs WHERE id = ?", (lid,)).fetchone()[0] == 45


def test_edit_invalid_minutes_keeps_data(client):
    log_one_page(client, 1, 30)
    lid = first_log_id(client)
    for bad in ("0", "abc", "", "601"):
        r = client.post(f"/historico/{lid}/editar", data={"minutes": bad, "day": "2026-11-06"},
                        follow_redirects=False)
        assert "erro=" in r.headers["location"], bad
    with open_db(client) as c:
        assert c.execute("SELECT minutes FROM logs WHERE id = ?", (lid,)).fetchone()[0] == 30


def test_edit_invalid_day_keeps_data(client):
    log_one_page(client, 1, 30)
    lid = first_log_id(client)
    r = client.post(f"/historico/{lid}/editar", data={"minutes": "30", "day": "2026-11-07"},
                    follow_redirects=False)
    assert "erro=" in r.headers["location"]


def test_reinforcement_listed(client):
    for page, m in ((1, 10), (2, 10), (3, 10), (4, 60)):
        log_one_page(client, page, m)
    html = client.get("/historico").text
    assert "Reforço" in html
    assert "2,7×" in html


def test_day_totals_vs_goal(client):
    log_one_page(client, 1, 30)
    assert "abaixo da meta" in client.get("/historico").text
    log_one_page(client, 2, 80)
    assert "dentro da meta" in client.get("/historico").text


def test_unknown_log_404(client):
    assert client.post("/historico/9999/apagar", follow_redirects=False).status_code == 404
    r = client.post("/historico/9999/editar", data={"minutes": "10", "day": "2026-11-06"},
                    follow_redirects=False)
    assert r.status_code == 404

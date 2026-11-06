from datetime import date

from app.db import get_setting
from tests.conftest import open_db

VALID = {
    "daily_goal_min": "120", "exam_date": "2026-12-12", "start_date": "2026-11-06",
    "alert_time": "19:00", "snooze_min": "20",
}


def setting(client, key):
    with open_db(client) as c:
        return get_setting(c, key)


def post(client, **over):
    return client.post("/config", data={**VALID, **over}, follow_redirects=False)


def test_config_page_shows_defaults(client):
    html = client.get("/config").text
    assert 'value="90"' in html
    assert 'value="2026-12-12"' in html
    assert 'value="2026-11-06"' in html  # início = hoje no primeiro uso
    assert "ainda não configurado" in html


def test_config_roundtrip(client):
    r = post(client)
    assert r.status_code == 303 and "ok=" in r.headers["location"]
    assert 'value="120"' in client.get("/config").text
    assert setting(client, "daily_goal_min") == "120"
    assert setting(client, "alert_time") == "19:00"
    assert setting(client, "snooze_min") == "20"


def test_config_validation_changes_nothing(client):
    for over in ({"daily_goal_min": "5"}, {"daily_goal_min": "abc"}, {"daily_goal_min": "601"},
                 {"exam_date": "2026-13-40"}, {"start_date": "ontem"},
                 {"alert_time": "25:99"}, {"alert_time": "7h"},
                 {"snooze_min": "0"}, {"snooze_min": "181"}):
        r = post(client, **over)
        assert r.status_code == 303, over
        assert "erro=" in r.headers["location"], over
    assert setting(client, "daily_goal_min") == "90"
    assert setting(client, "snooze_min") == "30"


def test_start_after_exam_is_rejected(client):
    r = post(client, start_date="2026-12-20")
    assert "erro=" in r.headers["location"]


def test_config_changes_dashboard(client):
    post(client, daily_goal_min="30")
    client.post("/teoria/fourier/registrar", data={
        "page_from": "1", "page_to": "1", "minutes": "30", "day": "2026-11-06"})
    assert "dentro da meta" in client.get("/").text

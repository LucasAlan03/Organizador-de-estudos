from datetime import date

import pytest

from app.logs import (
    LogError, add_item_log, add_page_range_log, delete_log, parse_minutes,
    recompute_day_status, update_log,
)
from tests.conftest import item_id

TODAY = date(2026, 11, 6)


def n_logs(conn):
    return conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]


def day_status(conn, day):
    row = conn.execute("SELECT status FROM days WHERE day = ?", (day,)).fetchone()
    return row["status"] if row else None


def test_parse_minutes_accepts_comma():
    assert parse_minutes("1,5") == 1.5
    assert parse_minutes("45") == 45.0


@pytest.mark.parametrize("raw", ["", "abc", "0", "-3", "601", "   "])
def test_parse_minutes_rejects(raw):
    with pytest.raises(LogError):
        parse_minutes(raw)


def test_page_range_splits_equally(catconn):
    results = add_page_range_log(catconn, "fourier", 2, 4, 90, TODAY, TODAY)
    assert len(results) == 3
    rows = catconn.execute("SELECT minutes FROM logs").fetchall()
    assert [r["minutes"] for r in rows] == [30, 30, 30]


@pytest.mark.parametrize("a,b", [(4, 2), (1, 8), (0, 3)])
def test_page_range_rejects_inverted_and_out_of_range(catconn, a, b):
    with pytest.raises(LogError):
        add_page_range_log(catconn, "fourier", a, b, 30, TODAY, TODAY)
    assert n_logs(catconn) == 0


def test_review_flag(catconn):
    item = item_id(catconn, "fourier:e4:c")
    first = add_item_log(catconn, item, 20, TODAY, TODAY)
    second = add_item_log(catconn, item, 10, TODAY, TODAY)
    assert first.is_review is False
    assert second.is_review is True
    assert n_logs(catconn) == 2


def test_future_day_rejected(catconn):
    item = item_id(catconn, "fourier:e6")
    with pytest.raises(LogError):
        add_item_log(catconn, item, 10, date(2026, 11, 7), TODAY)
    assert n_logs(catconn) == 0


def test_unknown_item_rejected(catconn):
    with pytest.raises(LogError):
        add_item_log(catconn, 999999, 10, TODAY, TODAY)


def test_day_status_follows_logs(catconn):
    res = add_item_log(catconn, item_id(catconn, "fourier:e6"), 15, TODAY, TODAY)
    assert day_status(catconn, "2026-11-06") == "estudou"
    delete_log(catconn, res.log_id)
    assert day_status(catconn, "2026-11-06") == "pendente"


def test_recompute_keeps_skipped_without_logs(catconn):
    catconn.execute("INSERT INTO days(day, status) VALUES ('2026-11-05', 'pulou')")
    catconn.commit()
    recompute_day_status(catconn, date(2026, 11, 5))
    assert day_status(catconn, "2026-11-05") == "pulou"


def test_update_log_moves_day_status(catconn):
    res = add_item_log(catconn, item_id(catconn, "fourier:e6"), 15, TODAY, TODAY)
    update_log(catconn, res.log_id, 20, date(2026, 11, 5), TODAY)
    assert day_status(catconn, "2026-11-05") == "estudou"
    assert day_status(catconn, "2026-11-06") == "pendente"
    row = catconn.execute("SELECT minutes FROM logs WHERE id = ?", (res.log_id,)).fetchone()
    assert row["minutes"] == 20


def test_update_log_validates(catconn):
    res = add_item_log(catconn, item_id(catconn, "fourier:e6"), 15, TODAY, TODAY)
    with pytest.raises(LogError):
        update_log(catconn, res.log_id, 0, TODAY, TODAY)
    with pytest.raises(LogError):
        update_log(catconn, 424242, 10, TODAY, TODAY)

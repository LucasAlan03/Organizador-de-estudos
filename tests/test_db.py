from datetime import date

from app.db import ensure_start_date, get_setting, init_schema, set_setting


def test_init_schema_is_idempotent(conn):
    init_schema(conn)
    assert get_setting(conn, "exam_date") == "2026-12-12"
    assert get_setting(conn, "daily_goal_min") == "90"


def test_set_and_get_setting(conn):
    set_setting(conn, "daily_goal_min", "120")
    assert get_setting(conn, "daily_goal_min") == "120"


def test_ensure_start_date_sets_once(conn):
    assert ensure_start_date(conn, date(2026, 11, 6)) == date(2026, 11, 6)
    assert ensure_start_date(conn, date(2026, 11, 9)) == date(2026, 11, 6)

from datetime import date

from app.logs import add_item_log
from app.stats import (
    TopicProgress, dashboard, day_totals, ensure_weekly_goal, item_rows,
    recent_logs, topic_progress,
)
from tests.conftest import item_id

TODAY = date(2026, 11, 6)  # sexta-feira


def log(conn, key, minutes, day=TODAY, today=None):
    return add_item_log(conn, item_id(conn, key), minutes, day, today or day)


def seed_basic(conn, day=TODAY):
    for key, m in (("fourier:p1", 10), ("fourier:p2", 20), ("fourier:p3", 30),
                   ("fourier:e4:a", 15), ("fourier:e4:b", 15), ("fourier:e4:c", 15)):
        log(conn, key, m, day)


def test_dashboard_empty(catconn):
    d = dashboard(catconn, TODAY)
    assert d.verdict.kind == "insufficient"
    assert d.total_minutes == 0
    assert d.theory == (0, 41)
    assert d.exercises == (0, 111)
    assert d.days_left == 36
    assert d.next_item_label == "Página 1"
    assert d.within_goal is False
    assert d.week_goal is None


def test_dashboard_after_logs(catconn):
    seed_basic(catconn)
    d = dashboard(catconn, TODAY)
    assert d.total_minutes == 105
    assert d.today_minutes == 105
    assert d.within_goal is True
    assert d.theory == (3, 41)
    assert d.exercises == (3, 111)
    assert d.remaining_minutes is not None
    assert d.week_goal is not None
    assert d.next_item_label == "Página 4"


def test_dashboard_start_day_has_no_division_by_zero(catconn):
    seed_basic(catconn)
    d = dashboard(catconn, TODAY)  # hoje == início
    assert d.avg_per_day == 105


def test_dashboard_on_exam_day(catconn):
    seed_basic(catconn)
    d = dashboard(catconn, date(2026, 12, 12))
    assert d.verdict.kind == "exam_arrived"
    assert d.days_left == 0
    assert d.week_goal is None


def test_weekly_goal_is_fixed_for_the_week(catconn):
    seed_basic(catconn)
    monday = date(2026, 11, 9)
    g1 = ensure_weekly_goal(catconn, monday)
    assert g1 is not None
    # mais estudo na quarta não muda a meta da semana
    log(catconn, "fourier:e5:a", 20, date(2026, 11, 11))
    assert ensure_weekly_goal(catconn, date(2026, 11, 11)) == g1
    # na segunda seguinte recalcula
    g2 = ensure_weekly_goal(catconn, date(2026, 11, 16))
    assert g2 is not None and g2 != g1
    n = catconn.execute("SELECT COUNT(*) FROM weekly_goals").fetchone()[0]
    assert n == 2


def test_weekly_goal_not_stored_without_estimate(catconn):
    assert ensure_weekly_goal(catconn, date(2026, 11, 9)) is None
    assert catconn.execute("SELECT COUNT(*) FROM weekly_goals").fetchone()[0] == 0


def test_review_does_not_inflate_progress(catconn):
    log(catconn, "fourier:p1", 10)
    log(catconn, "fourier:p1", 5)
    d = dashboard(catconn, TODAY)
    assert d.theory[0] == 1
    assert d.total_minutes == 15


def test_topic_progress(catconn):
    first = topic_progress(catconn, "page")[0]
    assert first == TopicProgress("fourier", "Séries de Fourier", 0, 7)
    log(catconn, "fourier:p1", 10)
    assert topic_progress(catconn, "page")[0].done == 1
    assert topic_progress(catconn, "exercise")[0].total == 25


def test_day_totals_most_recent_first(catconn):
    log(catconn, "fourier:p1", 10, date(2026, 11, 5), TODAY)
    log(catconn, "fourier:p2", 20, TODAY)
    log(catconn, "fourier:p3", 5, TODAY)
    assert day_totals(catconn) == [("2026-11-06", 25), ("2026-11-05", 10)]


def test_item_rows(catconn):
    log(catconn, "fourier:p2", 12)
    log(catconn, "fourier:p2", 8)
    rows = item_rows(catconn, "fourier", "page")
    assert [r.label for r in rows][:3] == ["Página 1", "Página 2", "Página 3"]
    p2 = rows[1]
    assert p2.done is True and p2.minutes == 20
    assert rows[0].done is False and rows[0].minutes == 0


def test_recent_logs(catconn):
    log(catconn, "fourier:e4:c", 20)
    rows = recent_logs(catconn)
    assert len(rows) == 1
    r = rows[0]
    assert (r.label, r.topic_title, r.minutes, r.day) == (
        "Exercício 4 (c)", "Séries de Fourier", 20, "2026-11-06",
    )

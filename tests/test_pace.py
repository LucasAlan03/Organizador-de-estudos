from datetime import date
from itertools import count

import pytest

from app.pace import (
    ItemStat, avg_minutes_per_day, days_left, remaining_minutes, unit_estimates,
)

_ids = count(1)


def stat(kind, topic, minutes, pos=1):
    return ItemStat(
        item_id=next(_ids), kind=kind, topic_id=topic, position=pos,
        minutes=minutes, done=minutes > 0,
    )


def test_avg_minutes_per_day():
    assert avg_minutes_per_day(540, date(2026, 11, 6), date(2026, 11, 8)) == 180
    assert avg_minutes_per_day(540, date(2026, 11, 6), date(2026, 11, 6)) == 540


def test_estimate_uses_topic_when_enough():
    items = [stat("page", "fourier", m) for m in (10, 20, 30)]
    assert unit_estimates(items).for_item("page", "fourier") == 20


def test_estimate_falls_back_to_global():
    items = [stat("page", "fourier", m) for m in (10, 20, 30)]
    items += [stat("page", "onda", m) for m in (40, 60)]
    assert unit_estimates(items).for_item("page", "onda") == 32


def test_estimate_none_when_not_enough_data():
    items = [stat("page", "fourier", 10), stat("page", "fourier", 20)]
    assert unit_estimates(items).for_item("page", "fourier") is None


def test_estimate_ignores_pending_items():
    items = [stat("page", "fourier", m) for m in (10, 20, 30)]
    items += [stat("page", "fourier", 0) for _ in range(5)]
    assert unit_estimates(items).for_item("page", "fourier") == 20


def test_remaining_minutes():
    done = [stat("page", "x", 20)] * 3 + [stat("exercise", "x", 15)] * 3
    est = unit_estimates(done)
    pending = [stat("page", "x", 0), stat("page", "x", 0), stat("exercise", "x", 0)]
    assert remaining_minutes(pending, est) == 55
    assert remaining_minutes([], est) == 0.0


def test_remaining_none_without_estimate_for_a_kind():
    done = [stat("page", "x", 20)] * 3
    est = unit_estimates(done)
    pending = [stat("page", "x", 0), stat("exercise", "x", 0)]
    assert remaining_minutes(pending, est) is None


def test_days_left():
    exam = date(2026, 12, 12)
    assert days_left(date(2026, 12, 11), exam) == 1
    assert days_left(date(2026, 12, 12), exam) == 0
    assert days_left(date(2026, 12, 13), exam) == -1


# ---- Task 5: veredito e meta da semana ----
from app.pace import verdict, week_goal  # noqa: E402


def test_verdict_insufficient():
    assert verdict(None, 10, 50).kind == "insufficient"


def test_verdict_done():
    assert verdict(0.0, 10, 50).kind == "done"


@pytest.mark.parametrize("days", [0, -2])
def test_verdict_exam_arrived(days):
    assert verdict(100.0, days, 50).kind == "exam_arrived"


def test_verdict_three_branches():
    assert verdict(600, 10, 70).kind == "folga"
    assert verdict(600, 10, 60).kind == "manter"
    v = verdict(600, 10, 40)
    assert v.kind == "aumentar"
    assert v.required_per_day == 60
    assert "60 min/dia" in v.message


def test_verdict_zero_average_does_not_divide_by_zero():
    v = verdict(600, 10, 0)
    assert v.kind == "aumentar"


def test_week_goal():
    assert week_goal(600, 21) == 200
    assert week_goal(600, 3) == 600
    assert week_goal(None, 21) is None
    assert week_goal(600, 0) is None


# ---- Task 6: reforço e próximo item ----
from app.pace import next_item, reinforcement  # noqa: E402


def test_reinforcement_items():
    items = [stat("page", "a", m) for m in (10, 10, 10, 60)]
    flagged, _ = reinforcement(items)
    assert len(flagged) == 1
    assert flagged[0].item_id == items[3].item_id
    assert flagged[0].ratio == pytest.approx(60 / 22.5)


def test_reinforcement_needs_min_records():
    items = [stat("page", "a", 10), stat("page", "a", 100)]
    assert reinforcement(items) == ([], [])


def test_reinforcement_topics():
    items = [stat("page", "a", 60) for _ in range(3)]
    items += [stat("page", "b", 10) for _ in range(3)]
    _, topics = reinforcement(items)
    assert [(t.topic_id, t.kind) for t in topics] == [("a", "page")]
    assert topics[0].ratio == pytest.approx(60 / 35)


def test_reinforcement_sorted_by_ratio_desc():
    items = [stat("page", "a", m) for m in (10, 10, 10, 10, 50, 80)]
    flagged, _ = reinforcement(items)
    assert [f.ratio for f in flagged] == sorted((f.ratio for f in flagged), reverse=True)
    assert flagged[0].item_id == items[5].item_id


def test_next_item_order():
    order = ["fourier", "onda"]
    page_pending = stat("page", "fourier", 0, pos=2)
    ex1 = stat("exercise", "fourier", 0, pos=1)
    ex2 = stat("exercise", "fourier", 0, pos=2)
    onda = stat("page", "onda", 0, pos=1)
    done_page = stat("page", "fourier", 30, pos=1)
    # página pendente vem antes de exercícios
    assert next_item([ex1, page_pending, done_page, onda], order) == page_pending.item_id
    # só exercícios pendentes: menor position
    assert next_item([ex2, ex1, done_page, onda], order) == ex1.item_id
    # fourier todo feito: primeiro pendente de onda
    all_done = [stat("page", "fourier", 5), stat("exercise", "fourier", 5), onda]
    assert next_item(all_done, order) == onda.item_id
    # tudo feito
    assert next_item([stat("page", "fourier", 5)], order) is None

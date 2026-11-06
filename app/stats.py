"""Camada de dados do painel: lê o banco e usa as contas puras de `pace`."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from app import pace
from app.db import ensure_start_date, get_setting
from app.pace import ItemStat, Verdict

TOP_REINFORCEMENT = 5


@dataclass(frozen=True)
class TopicProgress:
    topic_id: str
    title: str
    done: int
    total: int


@dataclass(frozen=True)
class ItemRow:
    item_id: int
    label: str
    exercise: int | None
    sub: str | None
    page: int | None
    minutes: float
    done: bool


@dataclass(frozen=True)
class LogRow:
    log_id: int
    item_id: int
    label: str
    kind: str
    topic_title: str
    minutes: float
    day: str


@dataclass(frozen=True)
class ReinforcementView:
    label: str
    topic_title: str
    minutes: float
    ratio: float


@dataclass(frozen=True)
class ReinforcementTopicView:
    topic_title: str
    kind: str
    ratio: float


@dataclass(frozen=True)
class Dashboard:
    days_left: int
    total_minutes: float
    avg_per_day: float
    today_minutes: float
    daily_goal: int
    within_goal: bool
    theory: tuple[int, int]
    exercises: tuple[int, int]
    verdict: Verdict
    remaining_minutes: float | None
    week_goal: float | None
    week_minutes: float
    reinforcement_items: list[ReinforcementView]
    reinforcement_topics: list[ReinforcementTopicView]
    next_item_label: str | None
    next_item_topic: str | None


def item_stats(conn: sqlite3.Connection) -> list[ItemStat]:
    rows = conn.execute(
        "SELECT i.id, i.kind, i.topic_id, i.position, "
        "COALESCE(SUM(l.minutes), 0) AS minutes "
        "FROM items i LEFT JOIN logs l ON l.item_id = i.id GROUP BY i.id "
        "ORDER BY i.id"
    ).fetchall()
    return [
        ItemStat(r["id"], r["kind"], r["topic_id"], r["position"],
                 r["minutes"], r["minutes"] > 0)
        for r in rows
    ]


def topic_progress(conn: sqlite3.Connection, kind: str) -> list[TopicProgress]:
    rows = conn.execute(
        "SELECT t.id, t.title, COUNT(i.id) AS total, "
        "COALESCE(SUM(CASE WHEN EXISTS (SELECT 1 FROM logs l WHERE l.item_id = i.id) "
        "THEN 1 ELSE 0 END), 0) AS done "
        "FROM topics t LEFT JOIN items i ON i.topic_id = t.id AND i.kind = ? "
        "GROUP BY t.id ORDER BY t.position",
        (kind,),
    ).fetchall()
    return [TopicProgress(r["id"], r["title"], r["done"], r["total"]) for r in rows]


def item_rows(conn: sqlite3.Connection, topic_id: str, kind: str) -> list[ItemRow]:
    rows = conn.execute(
        "SELECT i.id, i.label, i.exercise, i.sub, i.page, "
        "COALESCE(SUM(l.minutes), 0) AS minutes "
        "FROM items i LEFT JOIN logs l ON l.item_id = i.id "
        "WHERE i.topic_id = ? AND i.kind = ? GROUP BY i.id ORDER BY i.position",
        (topic_id, kind),
    ).fetchall()
    return [
        ItemRow(r["id"], r["label"], r["exercise"], r["sub"], r["page"],
                r["minutes"], r["minutes"] > 0)
        for r in rows
    ]


def recent_logs(conn: sqlite3.Connection, limit: int = 200) -> list[LogRow]:
    rows = conn.execute(
        "SELECT l.id, l.item_id, i.label, i.kind, t.title AS topic_title, "
        "l.minutes, l.day "
        "FROM logs l JOIN items i ON i.id = l.item_id JOIN topics t ON t.id = i.topic_id "
        "ORDER BY l.day DESC, l.id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [
        LogRow(r["id"], r["item_id"], r["label"], r["kind"], r["topic_title"],
               r["minutes"], r["day"])
        for r in rows
    ]


def day_totals(conn: sqlite3.Connection, limit: int = 60) -> list[tuple[str, float]]:
    rows = conn.execute(
        "SELECT day, SUM(minutes) AS minutes FROM logs GROUP BY day "
        "ORDER BY day DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [(r["day"], r["minutes"]) for r in rows]


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _estimate_remaining(conn: sqlite3.Connection) -> float | None:
    items = item_stats(conn)
    return pace.remaining_minutes(items, pace.unit_estimates(items))


def _exam_date(conn: sqlite3.Connection) -> date:
    return date.fromisoformat(get_setting(conn, "exam_date"))


def ensure_weekly_goal(conn: sqlite3.Connection, today: date) -> float | None:
    """Meta da semana: fixada na primeira consulta de cada semana (segunda a domingo)."""
    week_start = _monday(today).isoformat()
    row = conn.execute(
        "SELECT minutes FROM weekly_goals WHERE week_start = ?", (week_start,)
    ).fetchone()
    if row is not None:
        return row["minutes"]
    goal = pace.week_goal(
        _estimate_remaining(conn), pace.days_left(today, _exam_date(conn))
    )
    if goal is None:
        return None
    conn.execute(
        "INSERT INTO weekly_goals(week_start, minutes) VALUES (?, ?)", (week_start, goal)
    )
    conn.commit()
    return goal


def _sum_minutes(conn: sqlite3.Connection, start: date, end: date) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(minutes), 0) AS m FROM logs WHERE day BETWEEN ? AND ?",
        (start.isoformat(), end.isoformat()),
    ).fetchone()
    return row["m"]


def reinforcement_views(
    conn: sqlite3.Connection, limit: int | None = None
) -> tuple[list[ReinforcementView], list[ReinforcementTopicView]]:
    """Itens e assuntos de reforço, já com rótulos para exibir."""
    items = item_stats(conn)
    flagged_items, flagged_topics = pace.reinforcement(items)
    labels = {
        r["id"]: (r["label"], r["topic_title"])
        for r in conn.execute(
            "SELECT i.id, i.label, t.title AS topic_title FROM items i "
            "JOIN topics t ON t.id = i.topic_id"
        )
    }
    topic_titles = {r["id"]: r["title"] for r in conn.execute("SELECT id, title FROM topics")}
    minutes = {i.item_id: i.minutes for i in items}
    item_views = [
        ReinforcementView(labels[r.item_id][0], labels[r.item_id][1], minutes[r.item_id], r.ratio)
        for r in flagged_items
    ]
    topic_views = [
        ReinforcementTopicView(topic_titles[t.topic_id], t.kind, t.ratio)
        for t in flagged_topics
    ]
    return item_views[:limit], topic_views[:limit]


def dashboard(conn: sqlite3.Connection, today: date) -> Dashboard:
    start = ensure_start_date(conn, today)
    first = conn.execute("SELECT MIN(day) AS d FROM logs").fetchone()["d"]
    if first is not None:
        start = min(start, date.fromisoformat(first))

    exam = _exam_date(conn)
    items = item_stats(conn)
    est = pace.unit_estimates(items)
    remaining = pace.remaining_minutes(items, est)
    left = pace.days_left(today, exam)
    total = sum(i.minutes for i in items)
    avg = pace.avg_minutes_per_day(total, start, today)
    goal_min = int(get_setting(conn, "daily_goal_min"))
    today_min = _sum_minutes(conn, today, today)

    labels = {
        r["id"]: (r["label"], r["topic_title"])
        for r in conn.execute(
            "SELECT i.id, i.label, t.title AS topic_title FROM items i "
            "JOIN topics t ON t.id = i.topic_id"
        )
    }
    reinforcement_items, reinforcement_topics = reinforcement_views(conn, TOP_REINFORCEMENT)

    order = [r["id"] for r in conn.execute("SELECT id FROM topics ORDER BY position")]
    nxt = pace.next_item(items, order)

    def progress(kind: str) -> tuple[int, int]:
        of_kind = [i for i in items if i.kind == kind]
        return sum(1 for i in of_kind if i.done), len(of_kind)

    return Dashboard(
        days_left=left,
        total_minutes=total,
        avg_per_day=avg,
        today_minutes=today_min,
        daily_goal=goal_min,
        within_goal=today_min >= goal_min,
        theory=progress("page"),
        exercises=progress("exercise"),
        verdict=pace.verdict(remaining, left, avg),
        remaining_minutes=remaining,
        week_goal=ensure_weekly_goal(conn, today),
        week_minutes=_sum_minutes(conn, _monday(today), today),
        reinforcement_items=reinforcement_items,
        reinforcement_topics=reinforcement_topics,
        next_item_label=labels[nxt][0] if nxt is not None else None,
        next_item_topic=labels[nxt][1] if nxt is not None else None,
    )

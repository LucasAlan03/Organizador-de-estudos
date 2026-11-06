"""Contas de ritmo e projeção. Funções puras, sem I/O."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Sequence

MIN_RECORDS = 3


@dataclass(frozen=True)
class ItemStat:
    item_id: int
    kind: str          # 'page' | 'exercise'
    topic_id: str
    position: int
    minutes: float     # total registrado no item
    done: bool         # minutes > 0


def avg_minutes_per_day(total_minutes: float, start: date, today: date) -> float:
    days = max((today - start).days + 1, 1)
    return total_minutes / days


def days_left(today: date, exam: date) -> int:
    return (exam - today).days


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


class Estimates:
    """Minutos esperados por unidade (página ou subitem), só com dados do usuário."""

    def __init__(self, by_topic: dict[tuple[str, str], float], by_kind: dict[str, float]):
        self._by_topic = by_topic
        self._by_kind = by_kind

    def for_item(self, kind: str, topic_id: str) -> float | None:
        if (kind, topic_id) in self._by_topic:
            return self._by_topic[(kind, topic_id)]
        return self._by_kind.get(kind)


def unit_estimates(items: Sequence[ItemStat], min_records: int = MIN_RECORDS) -> Estimates:
    per_topic: dict[tuple[str, str], list[float]] = defaultdict(list)
    per_kind: dict[str, list[float]] = defaultdict(list)
    for it in items:
        if it.done:
            per_topic[(it.kind, it.topic_id)].append(it.minutes)
            per_kind[it.kind].append(it.minutes)
    by_topic = {k: _mean(v) for k, v in per_topic.items() if len(v) >= min_records}
    by_kind = {k: _mean(v) for k, v in per_kind.items() if len(v) >= min_records}
    return Estimates(by_topic, by_kind)


def remaining_minutes(items: Sequence[ItemStat], est: Estimates) -> float | None:
    total = 0.0
    for it in items:
        if it.done:
            continue
        unit = est.for_item(it.kind, it.topic_id)
        if unit is None:
            return None
        total += unit
    return total

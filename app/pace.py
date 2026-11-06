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


# ---- Veredito e meta da semana ----
FOLGA = 0.9
MANTER = 1.1


@dataclass(frozen=True)
class Verdict:
    kind: str  # insufficient | done | exam_arrived | folga | manter | aumentar
    required_per_day: float | None
    message: str


def verdict(remaining: float | None, days: int, avg_per_day: float) -> Verdict:
    if remaining is None:
        return Verdict(
            "insufficient", None,
            "Dados insuficientes: registre mais itens para eu estimar o que falta.",
        )
    if remaining <= 0:
        return Verdict("done", 0.0, "Tudo feito. Bom trabalho!")
    if days <= 0:
        return Verdict("exam_arrived", None, "A prova chegou (ou já passou).")
    required = remaining / days
    n = round(required)
    if required <= FOLGA * avg_per_day:
        return Verdict("folga", required, f"Dá para folgar: você precisa de ~{n} min/dia.")
    if required <= MANTER * avg_per_day:
        return Verdict("manter", required, f"No caminho: mantenha ~{n} min/dia.")
    return Verdict(
        "aumentar", required, f"Aumente para ~{n} min/dia para fechar até 11/12."
    )


def week_goal(remaining: float | None, days: int) -> float | None:
    if remaining is None or days <= 0:
        return None
    return remaining / max(days / 7, 1.0)


# ---- Reforço e próximo item ----
REINFORCEMENT_FACTOR = 1.5


@dataclass(frozen=True)
class ReinforcementItem:
    item_id: int
    ratio: float


@dataclass(frozen=True)
class ReinforcementTopic:
    topic_id: str
    kind: str
    ratio: float


def reinforcement(
    items: Sequence[ItemStat],
    factor: float = REINFORCEMENT_FACTOR,
    min_records: int = MIN_RECORDS,
) -> tuple[list[ReinforcementItem], list[ReinforcementTopic]]:
    """Itens e assuntos que levam bem mais tempo que a média da própria natureza."""
    done_by_kind: dict[str, list[ItemStat]] = defaultdict(list)
    for it in items:
        if it.done:
            done_by_kind[it.kind].append(it)

    flagged_items: list[ReinforcementItem] = []
    flagged_topics: list[ReinforcementTopic] = []
    for kind, group in done_by_kind.items():
        if len(group) < min_records:
            continue
        global_mean = _mean([g.minutes for g in group])
        for it in group:
            if it.minutes > factor * global_mean:
                flagged_items.append(ReinforcementItem(it.item_id, it.minutes / global_mean))
        by_topic: dict[str, list[float]] = defaultdict(list)
        for it in group:
            by_topic[it.topic_id].append(it.minutes)
        for topic_id, minutes in by_topic.items():
            if len(minutes) >= min_records and _mean(minutes) > factor * global_mean:
                flagged_topics.append(
                    ReinforcementTopic(topic_id, kind, _mean(minutes) / global_mean)
                )
    flagged_items.sort(key=lambda r: r.ratio, reverse=True)
    flagged_topics.sort(key=lambda r: r.ratio, reverse=True)
    return flagged_items, flagged_topics


def next_item(items: Sequence[ItemStat], topic_order: Sequence[str]) -> int | None:
    """Primeiro item pendente: assunto na ordem; teoria antes de exercícios."""
    for topic_id in topic_order:
        pending = [i for i in items if i.topic_id == topic_id and not i.done]
        for kind in ("page", "exercise"):
            of_kind = sorted((i for i in pending if i.kind == kind), key=lambda i: i.position)
            if of_kind:
                return of_kind[0].item_id
    return None

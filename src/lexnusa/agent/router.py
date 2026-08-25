from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

STATUS_PATTERN = re.compile(r"\b(status|berlaku|dicabut|diubah|perubahan|mencabut|mengubah)\b", re.I)
COMPLEX_PATTERN = re.compile(r"\b(bandingkan|perbedaan|hubungan|konflik|antara|versus|vs\.?|dan)\b", re.I)
SPLIT_PATTERN = re.compile(r"\s+(?:dan|dengan|versus|vs\.?)\s+|\s*;\s*", re.I)


class Route(str, Enum):
    SIMPLE = "simple"
    STATUS = "status"
    COMPLEX = "complex"


@dataclass(frozen=True)
class QueryPlan:
    route: Route
    queries: tuple[str, ...]


def route_query(question: str) -> QueryPlan:
    question = " ".join(question.split())
    is_status = bool(STATUS_PATTERN.search(question))
    is_complex = bool(COMPLEX_PATTERN.search(question)) and len(question.split()) >= 6
    if is_complex:
        parts = [part.strip(" ,?.") for part in SPLIT_PATTERN.split(question) if part.strip(" ,?.")]
        queries = tuple(dict.fromkeys([question, *parts]))[:4]
        return QueryPlan(Route.COMPLEX, queries)
    if is_status:
        return QueryPlan(Route.STATUS, (question, f"{question} mencabut mengubah status berlaku"))
    return QueryPlan(Route.SIMPLE, (question,))

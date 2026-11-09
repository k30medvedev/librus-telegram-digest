"""Grade arithmetic."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import Grade


def grade_value(grade: str) -> float | None:
    """Numeric value of a grade: "4" -> 4.0, "3+" -> 3.5, "4-" -> 3.75, "np" -> None."""
    s = str(grade or "").strip()
    if not s[:1].isdigit():
        return None
    value = float(s[0])
    if s[1:2] == "+":
        value += 0.5
    elif s[1:2] == "-":
        value -= 0.25
    return value


def _weight(g: Grade) -> float:
    try:
        return float(str(g.weight if g.weight is not None else 1).replace(",", "."))
    except ValueError:
        return 1.0


def weighted_average(grades: Iterable[Grade]) -> float | None:
    """Weighted mean of the numeric grades that count towards the average."""
    total = weight_sum = 0.0
    for g in grades:
        value = grade_value(g.grade)
        if value is None or not g.counts:
            continue
        w = _weight(g)
        total += value * w
        weight_sum += w
    return total / weight_sum if weight_sum else None


@dataclass(frozen=True)
class AverageChange:
    subject: str
    before: float | None   # None if there were no counted grades before
    after: float


def average_changes(all_grades: list[Grade], new_grades: list[Grade]) -> list[AverageChange]:
    """For every subject with new grades: the average before and after them.

    Only the latest semester that contains a new grade for the subject is considered.
    """
    new_keys = {g.key for g in new_grades}
    out: list[AverageChange] = []
    for subject in sorted({g.subject for g in new_grades}):
        semester = max(g.semester for g in new_grades if g.subject == subject)
        current = [g for g in all_grades if g.subject == subject and g.semester == semester]
        after = weighted_average(current)
        if after is None:
            continue
        before = weighted_average([g for g in current if g.key not in new_keys])
        out.append(AverageChange(subject=subject, before=before, after=after))
    return out

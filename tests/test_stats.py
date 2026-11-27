import pytest

from librus_digest.models import Grade
from librus_digest.stats import average_changes, grade_value, weighted_average


def g(key, grade, subject="Math", weight=1, counts=True, semester=0):
    return Grade(key=key, subject=subject, grade=grade, date="2026-01-01",
                 weight=weight, counts=counts, semester=semester)


@pytest.mark.parametrize("raw, expected", [
    ("5", 5.0), ("3+", 3.5), ("4-", 3.75), (" 2 ", 2.0),
    ("np", None), ("+", None), ("", None), (None, None),
])
def test_grade_value(raw, expected):
    assert grade_value(raw) == expected


def test_weighted_average_uses_weights():
    # (5*1 + 3*3) / 4
    assert weighted_average([g("a", "5", weight=1), g("b", "3", weight=3)]) == pytest.approx(3.5)


def test_weighted_average_skips_uncounted_and_non_numeric():
    grades = [g("a", "5"), g("b", "1", counts=False), g("c", "np")]
    assert weighted_average(grades) == 5.0


def test_weighted_average_empty_is_none():
    assert weighted_average([]) is None
    assert weighted_average([g("a", "np")]) is None


def test_weighted_average_tolerates_bad_or_missing_weight():
    assert weighted_average([g("a", "4", weight=None), g("b", "2", weight="x")]) == 3.0
    assert weighted_average([g("a", "4", weight="2,5")]) == 4.0


def test_average_changes_before_and_after():
    old = [g("a", "4"), g("b", "4")]
    new = [g("c", "5")]
    (change,) = average_changes(old + new, new)
    assert change.subject == "Math"
    assert change.before == 4.0
    assert change.after == pytest.approx(13 / 3)


def test_average_changes_first_grade_has_no_before():
    new = [g("a", "3")]
    (change,) = average_changes(new, new)
    assert change.before is None and change.after == 3.0


def test_average_changes_only_latest_semester_and_per_subject():
    grades = [
        g("a", "1", semester=0),                      # old semester, ignored
        g("b", "5", semester=1), g("c", "3", semester=1),
        g("d", "2", subject="Art", semester=1),
    ]
    new = [grades[2], grades[3]]
    changes = {c.subject: c for c in average_changes(grades, new)}
    assert changes["Math"].before == 5.0 and changes["Math"].after == 4.0
    assert changes["Art"].before is None

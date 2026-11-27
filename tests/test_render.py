from datetime import datetime

import pytest

from librus_digest.models import (Announcement, Attendance, CalendarEvent, Grade,
                                  Homework, Lesson, Message)
from librus_digest.render import Renderer, cap, esc, grade_comment, short_words
from librus_digest.stats import AverageChange

EN = Renderer("en")
RU = Renderer("ru")


def grade(**kw):
    base = dict(key="k", subject="chemia", grade="4", date="2026-11-06", category="kartkówka")
    return Grade(**{**base, **kw})


def test_helpers():
    assert esc("<b> & ") == "&lt;b&gt; &amp;"
    assert esc(None) == ""
    assert cap("chemia") == "Chemia" and cap("") == ""
    assert short_words("a b c d", 2) == "a b…"
    assert short_words("a b", 5) == "a b"


def test_grade_comment_strips_trailing_teacher_and_date():
    g = grade(description="Ocena: 3\nKomentarz: Czynniki w pracy. Nowak Anna 2026-11-06",
              teacher="Nowak Anna")
    assert grade_comment(g) == "Czynniki w pracy"


def test_grade_comment_missing_or_truncated():
    assert grade_comment(grade(description="no comment here")) == ""
    long = grade(description="Komentarz: " + "word " * 100)
    assert grade_comment(long).endswith("…") and len(grade_comment(long)) <= 141


@pytest.mark.parametrize("value, dot", [("6", "🟢"), ("5", "🟢"), ("4", "🔵"), ("3+", "🟡"),
                                         ("1", "🔴"), ("np", "⚪")])
def test_grade_dot(value, dot):
    assert EN.grade(grade(grade=value)).startswith(dot)


def test_grade_line_shows_weight_and_not_counted():
    text = EN.grade(grade(weight=2, counts=False))
    assert "weight 2" in text and "(not counted)" in text
    assert "вес 2" in RU.grade(grade(weight=2))


def test_grade_escapes_html():
    assert "&lt;script&gt;" in EN.grade(grade(subject="<script>"))


def test_average_change_formats():
    assert EN.average_change(AverageChange("chemia", None, 3.0)) == "Chemia: 3,00"
    assert EN.average_change(AverageChange("chemia", 4.1, 4.0)) == "Chemia: 4,10 → <b>4,00</b>"
    assert "(unchanged)" in EN.average_change(AverageChange("chemia", 4.0, 4.0))


def test_attendance_icons():
    late = Attendance(symbol="sp", type="spóźnienie", subject="fizyka", period=2, date="2026-11-06")
    absent = Attendance(symbol="nb", type="nieobecność", subject="fizyka", period=3, date="2026-11-06")
    assert EN.attendance(late).startswith("⏰") and EN.attendance(absent).startswith("❌")
    assert "lesson 2" in EN.attendance(late)


def test_clean_author_collapses_duplicate_name_and_translates_role():
    assert EN.clean_author("Smith John (Smith John) [Nauczyciel]") == "Smith John (teacher)"
    assert RU.clean_author("Smith John (Smith John) [Nauczyciel]") == "Smith John (учитель)"
    assert EN.clean_author("Parent (Other Name)") == "Parent (Other Name)"


def test_message_with_and_without_body():
    m = Message(href="h", title="Meeting", author="A (A)", date="2026-11-06 08:23:11")
    with_body = EN.message(m, "hello " * 200, max_words=5)
    assert "<blockquote>hello hello hello hello hello…</blockquote>" in with_body
    assert "2026-11-06 08:23" in with_body and "08:23:11" not in with_body
    assert "<blockquote>" not in EN.message(m, "")


def test_announcement_truncates():
    a = Announcement(title="T", author="A", date="2026-11-06", description="w " * 100)
    assert EN.announcement(a, max_words=3).count("w") == 3


def test_upcoming_exam_holiday_and_homework():
    exam = CalendarEvent(date=datetime(2026, 11, 10), kind="exam", subject="chemia",
                         title="sprawdzian", lesson=6, description="bonds " * 30)
    quiz = CalendarEvent(date=datetime(2026, 11, 12), kind="exam", subject="polski", title="kartkówka")
    day_off = CalendarEvent(date=datetime(2026, 11, 11), kind="holiday", subject="", title="Independence Day")
    lines = EN.upcoming([exam, day_off, quiz], [Homework("fizyka", "worksheet", "2026-11-12")])
    assert lines[0].startswith("<b>Tue 10.11</b>  🔴 Chemia — sprawdzian, lesson 6")
    assert "bonds" in lines[0] and "…" in lines[0]
    assert lines[1] == "<b>Wed 11.11</b>  day off: Independence Day"
    assert "🟡" in lines[2]
    assert lines[3].startswith("<b>Homework due 2026-11-12</b>")


def test_school_day_variants():
    lessons = [Lesson(2, "English", "08:50", "09:35"), Lesson(5, "Polish", "11:35", "12:20")]
    monday = datetime(2026, 11, 9)
    tomorrow = EN.school_day(monday, lessons, days_ahead=1, tomorrow_is_weekend=False)
    assert "Tomorrow, Monday 09.11" in tomorrow and "from <b>08:50</b> to <b>12:20</b>, 2 lessons" in tomorrow
    assert "First lesson: #2, English" in tomorrow and "No school" not in tomorrow

    weekend = EN.school_day(monday, lessons, days_ahead=3, tomorrow_is_weekend=True)
    assert "No school tomorrow." in weekend and "Next school day — Monday 09.11" in weekend

    assert "No lessons" in EN.school_day(None, [], 0, False)


def test_header_and_languages():
    friday = datetime(2026, 11, 6)
    assert EN.header(friday) == "<b>Digest · Friday, November 6</b>"
    assert RU.header(friday) == "<b>Сводка · пятница, 6 ноября</b>"
    assert Renderer("xx").header(friday) == EN.header(friday)   # unknown -> English


def test_section_empty_is_empty_string():
    assert EN.section("Title", []) == ""
    assert EN.section("Title", ["a", "b"]) == "<b>Title</b>\na\nb"

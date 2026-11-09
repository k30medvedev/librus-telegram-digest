from datetime import datetime

from librus_digest.config import Account, Settings
from librus_digest.digest import build_account_report, next_school_day, run_digest
from librus_digest.models import (Announcement, Attendance, CalendarEvent, Grade, Lesson,
                                  Message)
from librus_digest.render import Renderer

FRIDAY = datetime(2026, 11, 6, 19, 0)
TODAY = "2026-11-06"


class FakeSession:
    """Stands in for LibrusSession; every method can be overridden or made to fail."""

    def __init__(self, **overrides):
        self.data = dict(
            grades=[], attendance=[], messages=[], announcements=[],
            calendar_events=[], homework=[],
            timetable={datetime(2026, 11, 9): [[Lesson(1, "Math", "08:00", "08:45")], [], [], [], []]},
        )
        self.data.update(overrides)
        self.opened = []

    def _get(self, name):
        value = self.data[name]
        if isinstance(value, Exception):
            raise value
        return value

    def grades(self): return self._get("grades")
    def attendance(self): return self._get("attendance")
    def messages(self): return self._get("messages")
    def announcements(self): return self._get("announcements")
    def calendar_events(self, start, end): return self._get("calendar_events")
    def homework(self, start, end): return self._get("homework")

    def message_body(self, href):
        self.opened.append(href)
        return "body of " + href

    def timetable_week(self, monday):
        return self._get("timetable").get(monday, [[], [], [], [], []])


def make_grade(key, value, date=TODAY, subject="Math"):
    return Grade(key=key, subject=subject, grade=value, date=date, weight=1)


def report(session, language="en"):
    return build_account_report(session, "Anna", Renderer(language), FRIDAY)


def test_quiet_day_says_so_and_confirms_no_absences():
    text = report(FakeSession()).text
    assert text.startswith("<b>ANNA</b>")
    assert "No new grades or messages." in text
    assert "✅ None today" in text
    assert "Next school day — Monday 09.11" in text


def test_only_todays_grades_are_listed_with_average():
    session = FakeSession(grades=[make_grade("old", "2", date="2026-11-01"),
                                  make_grade("new", "5")])
    text = report(session).text
    assert "<b>5</b>" in text and "<b>2</b>" not in text
    assert "Math: 2,00 → <b>3,50</b>" in text
    assert "No new grades" not in text


def test_absence_today_is_listed_and_old_ones_are_not():
    absent = Attendance("nb", "nieobecność", "fizyka", 3, TODAY)
    old = Attendance("nb", "nieobecność", "chemia", 1, "2026-10-01")
    text = report(FakeSession(attendance=[absent, old])).text
    assert "Fizyka" in text and "Chemia" not in text and "✅" not in text


def test_messages_are_opened_and_previewed_only_if_from_today():
    session = FakeSession(messages=[
        Message("h1", "Today", "A", f"{TODAY} 08:00:00"),
        Message("h2", "Old", "A", "2026-11-01 08:00:00"),
    ])
    text = report(session).text
    assert "body of h1" in text and "Old" not in text
    assert session.opened == ["h1"]


def test_optional_sources_failing_do_not_break_the_report():
    session = FakeSession(announcements=RuntimeError("x"), calendar_events=RuntimeError("y"),
                          homework=RuntimeError("z"))
    result = report(session)
    assert "ANNA" in result.text and result.announcements == []


def test_core_source_failure_propagates():
    import pytest
    with pytest.raises(RuntimeError):
        report(FakeSession(grades=RuntimeError("login failed")))


def test_upcoming_section_appears_when_there_are_events():
    event = CalendarEvent(datetime(2026, 11, 10), "exam", "chemia", "sprawdzian", lesson=6)
    assert "Coming up" in report(FakeSession(calendar_events=[event])).text
    assert "Coming up" not in report(FakeSession()).text


def test_next_school_day_skips_weekend_and_empty_days():
    day, lessons, ahead = next_school_day(FakeSession(), FRIDAY)
    assert day == datetime(2026, 11, 9) and ahead == 3 and lessons[0].subject == "Math"


def test_next_school_day_none_when_no_lessons_in_horizon():
    assert next_school_day(FakeSession(timetable={}), FRIDAY) == (None, [], 0)


def test_next_school_day_survives_timetable_errors():
    assert next_school_day(FakeSession(timetable=RuntimeError("down")), FRIDAY) == (None, [], 0)


def settings(accounts, language="en"):
    return Settings(telegram_token="t", chat_ids=("1",), accounts=tuple(accounts), language=language)


def test_run_digest_sends_one_message_per_student_header_only_on_first():
    sent = []
    sessions = {"1": FakeSession(), "2": FakeSession()}
    messages = run_digest(
        settings([Account("Anna", "1", "p"), Account("Ben", "2", "p")]),
        session_factory=lambda login, pw: sessions[login], send=sent.append, now=FRIDAY)
    assert sent == messages and len(sent) == 2
    assert sent[0].startswith("<b>Digest · Friday, November 6</b>") and "ANNA" in sent[0]
    assert sent[1].startswith("<b>BEN</b>")


def test_run_digest_deduplicates_announcements_between_students():
    news = Announcement("Closed", "Principal", TODAY, "Library moved")
    sessions = {"1": FakeSession(announcements=[news]), "2": FakeSession(announcements=[news])}
    messages = run_digest(
        settings([Account("Anna", "1", "p"), Account("Ben", "2", "p")]),
        session_factory=lambda login, pw: sessions[login], send=lambda t: None, now=FRIDAY)
    assert len(messages) == 3
    assert messages[-1].count("Library moved") == 1 and "School announcements" in messages[-1]


def test_run_digest_reports_a_failing_account_and_continues():
    def factory(login, password):
        if login == "1":
            raise ConnectionError("Librus is down")
        return FakeSession()

    messages = run_digest(settings([Account("Anna", "1", "secret-pw"), Account("Ben", "2", "p")]),
                          session_factory=factory, send=lambda t: None, now=FRIDAY)
    assert "Anna" in messages[0] and "ConnectionError" in messages[0]
    assert "secret-pw" not in "".join(messages)
    assert messages[1].startswith("<b>BEN</b>")

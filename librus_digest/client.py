"""Adapter around the unofficial `librus-apix` scraper.

This is the only module that talks to Librus. Everything else works on the plain
dataclasses from :mod:`librus_digest.models`, which keeps it easy to test and to
swap the data source if the scraper ever breaks.
"""
from __future__ import annotations

import re
from datetime import datetime

from librus_apix.announcements import get_announcements
from librus_apix.attendance import get_attendance
from librus_apix.client import new_client
from librus_apix.grades import get_grades
from librus_apix.homework import get_homework
from librus_apix.messages import get_received, message_content
from librus_apix.schedule import get_schedule
from librus_apix.timetable import get_timetable

from .models import (Announcement, Attendance, CalendarEvent, Grade, Homework,
                     Lesson, Message)


class LibrusSession:
    """A logged-in Librus Synergia session for one account."""

    def __init__(self, login: str, password: str):
        self._client = new_client()
        self._client.get_token(login, password)

    # -- grades ---------------------------------------------------------

    def grades(self) -> list[Grade]:
        numeric, _averages, descriptive = get_grades(self._client, "all")
        out: list[Grade] = []
        for sem, semester in enumerate(numeric):
            for subject, items in semester.items():
                for g in items:
                    out.append(Grade(
                        key=g.href or f"{subject}|{g.grade}|{g.date}|{g.category}|{g.title}",
                        subject=subject, grade=g.grade, date=g.date, category=g.category,
                        title=g.title, weight=g.weight, counts=g.counts,
                        description=g.desc or "", teacher=g.teacher or "", semester=sem,
                    ))
        for sem, semester in enumerate(descriptive):
            for subject, items in semester.items():
                for g in items:
                    out.append(Grade(
                        key=g.href or f"{subject}|{g.grade}|{g.date}|{g.title}",
                        subject=subject, grade=g.grade, date=g.date, category="descriptive",
                        title=g.title, counts=False, description=g.desc or "",
                        teacher=g.teacher or "", semester=sem,
                    ))
        return out

    # -- attendance -----------------------------------------------------

    def attendance(self) -> list[Attendance]:
        """Everything except plain presence ("ob")."""
        return [
            Attendance(symbol=a.symbol, type=a.type, subject=a.subject,
                       period=a.period, date=a.date)
            for semester in get_attendance(self._client, "all")
            for a in semester if a.symbol != "ob"
        ]

    # -- messages and announcements ---------------------------------------

    def messages(self) -> list[Message]:
        """First page of the inbox."""
        return [Message(href=m.href, title=m.title, author=m.author, date=m.date)
                for m in get_received(self._client, 0) if m.href]

    def message_body(self, href: str) -> str:
        """Note: opening a message marks it as read in Librus."""
        return message_content(self._client, href).content

    def announcements(self) -> list[Announcement]:
        return [Announcement(title=a.title, author=a.author, date=a.date,
                             description=a.description)
                for a in get_announcements(self._client)]

    # -- calendar, homework, timetable ------------------------------------

    def calendar_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        """Exams/quizzes and non-teaching days in [start, end)."""
        months = {(start.year, start.month), (end.year, end.month)}
        out: list[CalendarEvent] = []
        for year, month in sorted(months):
            schedule = get_schedule(self._client, str(month), str(year))
            for day, events in schedule.items():
                try:
                    date = datetime(year, month, int(day))
                except ValueError:
                    continue
                if not start <= date < end:
                    continue
                for e in events:
                    out.append(_to_calendar_event(date, e))
        return sorted((e for e in out if e is not None), key=lambda e: e.date)

    def homework(self, start: datetime, end: datetime) -> list[Homework]:
        return [Homework(subject=h.subject, lesson=h.lesson, due=h.completion_date)
                for h in get_homework(self._client, start.strftime("%Y-%m-%d"),
                                      end.strftime("%Y-%m-%d"))]

    def timetable_week(self, monday: datetime) -> list[list[Lesson]]:
        """Lessons per weekday (index 0 = Monday) for the week starting *monday*."""
        week = get_timetable(self._client, monday)
        return [[Lesson(number=p.number, subject=p.subject, start=p.date_from, end=p.date_to)
                 for p in day if p.subject] for day in week]


def _to_calendar_event(date: datetime, e) -> CalendarEvent | None:
    href = e.href or ""
    title = (e.title or "").strip()
    if "wolne" in href:  # day off, e.g. a public holiday
        return CalendarEvent(date=date, kind="holiday", subject="",
                             title=re.sub(r":\s*\w+$", "", title))
    if not href.startswith("szczegoly/"):
        return None  # substitutions and cancelled lessons are not shown
    data = e.data if isinstance(e.data, dict) else {}
    description = str(data.get("Opis") or "")
    lesson = int(e.number) if str(e.number).isdigit() and int(e.number) > 0 else None
    return CalendarEvent(date=date, kind="exam", subject=e.subject or "", title=title,
                         lesson=lesson,
                         description="" if description == "unknown" else description)

"""Plain data models, independent of the scraping library."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Grade:
    key: str            # unique id (Librus detail link)
    subject: str
    grade: str          # "5", "3+", "np", ...
    date: str           # YYYY-MM-DD
    category: str = ""
    title: str = ""
    weight: str | int | None = None
    counts: bool = True
    description: str = ""
    teacher: str = ""
    semester: int = 0


@dataclass(frozen=True)
class Attendance:
    symbol: str         # "nb" absent, "sp" late, ...
    type: str
    subject: str
    period: int | str
    date: str


@dataclass(frozen=True)
class Message:
    href: str
    title: str
    author: str
    date: str           # "YYYY-MM-DD HH:MM:SS"


@dataclass(frozen=True)
class Announcement:
    title: str
    author: str
    date: str
    description: str


@dataclass(frozen=True)
class Homework:
    subject: str
    lesson: str
    due: str


@dataclass(frozen=True)
class CalendarEvent:
    date: object        # datetime.datetime
    kind: str           # "exam" or "holiday"
    subject: str
    title: str
    lesson: int | None = None
    description: str = ""


@dataclass(frozen=True)
class Lesson:
    number: int | str
    subject: str
    start: str
    end: str

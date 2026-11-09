"""Turn data into Telegram HTML. Pure functions: no network, no clock."""
from __future__ import annotations

import html
import re
from datetime import datetime

from .i18n import get_strings
from .models import (Announcement, Attendance, CalendarEvent, Grade, Homework,
                     Lesson, Message)
from .stats import AverageChange

GRADE_DOTS = {"6": "🟢", "5": "🟢", "4": "🔵", "3": "🟡", "2": "🔴", "1": "🔴"}
SEPARATOR = "──────────────"


def esc(value) -> str:
    return html.escape(str(value or "").strip())


def cap(value) -> str:
    s = str(value or "").strip()
    return s[:1].upper() + s[1:]


def short_words(text, limit: int) -> str:
    """First *limit* words of *text*, with an ellipsis if it was cut."""
    words = str(text or "").split()
    return " ".join(words[:limit]) + ("…" if len(words) > limit else "")


def format_avg(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def grade_comment(g: Grade) -> str:
    """The teacher's comment from the grade details, without the trailing 'Teacher date'."""
    if "Komentarz:" not in g.description:
        return ""
    comment = " ".join(g.description.split("Komentarz:", 1)[1].split())
    tail = f"{g.teacher} {g.date}".strip()
    if tail and comment.endswith(tail):
        comment = comment[: -len(tail)].strip()
    comment = comment.rstrip(" .…")
    return comment[:140] + ("…" if len(comment) > 140 else "")


class Renderer:
    def __init__(self, language: str = "en"):
        self.t = get_strings(language)

    # -- small pieces -------------------------------------------------------

    def section(self, title: str, items: list[str], icon: str = "") -> str:
        """A bold title (with an optional leading emoji) followed by the items."""
        if not items:
            return ""
        prefix = f"{icon} " if icon else ""
        return f"{prefix}<b>{title}</b>\n" + "\n".join(items)

    def clean_author(self, author: str) -> str:
        """'Smith John (Smith John) [Nauczyciel]' -> 'Smith John (teacher)'."""
        a = str(author or "")
        m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*(\[[^\]]*\])?\s*$", a)
        if m and m.group(1).strip() == m.group(2).strip():
            a = m.group(1).strip() + (" " + m.group(3) if m.group(3) else "")
        return a.replace("[Nauczyciel]", self.t["teacher"]).strip()

    # -- sections -----------------------------------------------------------

    def grade(self, g: Grade) -> str:
        dot = GRADE_DOTS.get(str(g.grade).strip()[:1], "⚪")
        not_counted = f" {self.t['not_counted']}" if not g.counts else ""
        what = str(g.category or g.title or "").strip()
        weight = f", {self.t['weight'].format(w=g.weight)}" if g.weight else ""
        line = (f"{dot} <b>{esc(g.grade)}</b>  {esc(cap(g.subject))}{not_counted}\n"
                f"      <i>{esc(what)}{weight}</i>")
        comment = grade_comment(g)
        return line + (f"\n      {esc(comment)}" if comment else "")

    def average_change(self, c: AverageChange) -> str:
        name = esc(cap(c.subject))
        if c.before is None:
            return f"{name}: {format_avg(c.after)}"
        if abs(c.before - c.after) < 0.005:
            return f"{name}: {format_avg(c.after)} {self.t['unchanged']}"
        return f"{name}: {format_avg(c.before)} → <b>{format_avg(c.after)}</b>"

    def attendance(self, a: Attendance) -> str:
        icon = "⏰" if a.symbol == "sp" else "❌"
        return (f"{icon} <b>{esc(cap(a.type))}</b>  {esc(cap(a.subject))}\n"
                f"      <i>{esc(self.t['lesson'].format(n=a.period))}, {esc(a.date)}</i>")

    def message(self, m: Message, body: str = "", max_words: int = 100) -> str:
        text = f"<b>{esc(m.title)}</b>\n<i>{esc(self.clean_author(m.author))}, {esc(m.date[:16])}</i>"
        body = short_words(body, max_words)
        return text + (f"\n<blockquote>{esc(body)}</blockquote>" if body else "")

    def announcement(self, a: Announcement, max_words: int = 60) -> str:
        return (f"<b>{esc(a.title)}</b>\n<i>{esc(a.author)}, {esc(a.date)}</i>\n"
                f"<blockquote>{esc(short_words(a.description, max_words))}</blockquote>")

    def upcoming(self, events: list[CalendarEvent], homework: list[Homework]) -> list[str]:
        t = self.t
        lines = []
        for e in events:
            day = f"<b>{t['weekdays_short'][e.date.weekday()]} {e.date:%d.%m}</b>"
            if e.kind == "holiday":
                lines.append(f"{day}  {esc(t['holiday'].format(name=e.title))}")
                continue
            lowered = e.title.lower()
            icon = "🔴" if ("sprawdzian" in lowered or "klasow" in lowered) else (
                "🟡" if "kartk" in lowered else "▫️")
            lesson = f", {t['lesson'].format(n=e.lesson)}" if e.lesson else ""
            line = f"{day}  {icon} {esc(cap(e.subject))} — {esc(e.title)}{lesson}"
            if e.description:
                line += f"\n    <i>{esc(short_words(e.description, 14))}</i>"
            lines.append(line)
        for h in homework:
            lines.append(f"<b>{esc(t['homework_due'].format(date=h.due))}</b>  "
                         f"{esc(cap(h.subject))} — {esc(short_words(h.lesson, 12))}")
        return lines

    def school_day(self, day: datetime | None, lessons: list[Lesson],
                   days_ahead: int, tomorrow_is_weekend: bool) -> str:
        t = self.t
        title = f"🏫 <b>{t['school']}</b>\n"
        if day is None:
            return title + t["no_lessons"]
        weekday = t["weekdays"][day.weekday()]
        when = (t["tomorrow"] if days_ahead == 1 else t["next_day"]).format(
            weekday=weekday, date=f"{day:%d.%m}")
        first, last = lessons[0], lessons[-1]
        times = t["times"].format(start=esc(first.start), end=esc(last.end), n=len(lessons))
        first_lesson = t["first_lesson"].format(n=esc(first.number), subject=esc(first.subject))
        off = f"{t['tomorrow_off']}\n" if tomorrow_is_weekend else ""
        return f"{title}{off}{when}: {times}\n<i>{first_lesson}</i>"

    def header(self, now: datetime) -> str:
        return "<b>" + self.t["digest_title"].format(
            weekday=self.t["weekdays"][now.weekday()],
            day=now.day, month=self.t["months"][now.month - 1]) + "</b>"

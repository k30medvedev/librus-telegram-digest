"""Build and send the daily digest."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

from .config import Settings
from .models import Announcement, Lesson
from .render import Renderer, esc
from .stats import average_changes
from .telegram import send_message

log = logging.getLogger(__name__)

UPCOMING_DAYS = 10


@dataclass
class AccountReport:
    text: str
    announcements: list[Announcement] = field(default_factory=list)


def _safe(what: str, func: Callable, default):
    """Run *func*; on failure log it and return *default* so one broken page
    does not take the whole digest down."""
    try:
        return func()
    except Exception as exc:  # noqa: BLE001 - scraper errors are unpredictable
        log.warning("%s unavailable: %s", what, exc)
        return default


def next_school_day(session, now: datetime, horizon: int = UPCOMING_DAYS):
    """First weekday after today that has lessons: (date, lessons, days_ahead)."""
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    weeks: dict[datetime, list[list[Lesson]]] = {}
    for ahead in range(1, horizon + 1):
        day = today + timedelta(days=ahead)
        if day.weekday() >= 5:
            continue
        monday = day - timedelta(days=day.weekday())
        if monday not in weeks:
            weeks[monday] = _safe(f"timetable {monday:%Y-%m-%d}",
                                  lambda m=monday: session.timetable_week(m), [])
        week = weeks[monday]
        lessons = week[day.weekday()] if len(week) > day.weekday() else []
        if lessons:
            return day, lessons, ahead
    return None, [], 0


def build_account_report(session, name: str, renderer: Renderer, now: datetime) -> AccountReport:
    """Everything that happened *today* for one student, plus what is coming up."""
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    horizon = tomorrow + timedelta(days=UPCOMING_DAYS)
    t = renderer.t

    all_grades = session.grades()
    new_grades = [g for g in all_grades if g.date == today]
    absences = [a for a in session.attendance() if a.date == today]
    messages = [m for m in session.messages() if m.date.startswith(today)]
    announcements = [a for a in _safe("announcements", session.announcements, [])
                     if a.date == today]
    events = _safe("calendar", lambda: session.calendar_events(tomorrow, horizon), [])
    homework = _safe("homework", lambda: session.homework(tomorrow, horizon), [])

    def body(href: str) -> str:
        return _safe(f"message {href}", lambda: session.message_body(href), "")

    blocks = [f"<b>{esc(name.upper())}</b>"]
    if not new_grades and not messages:
        blocks.append(t["no_news"])
    if new_grades:
        blocks.append(renderer.section(t["grades"], [renderer.grade(g) for g in new_grades], "📝"))
        changes = average_changes(all_grades, new_grades)
        blocks.append(renderer.section(t["average"], [renderer.average_change(c) for c in changes]))
    blocks.append(
        renderer.section(t["attendance"], [renderer.attendance(a) for a in absences], "🚫")
        or f"🚫 <b>{t['attendance']}</b>\n✅ {t['attendance_none']}")
    if messages:
        blocks.append(renderer.section(
            t["messages"], [renderer.message(m, body(m.href)) for m in messages], "✉️"))
    upcoming = renderer.upcoming(events, homework)
    if upcoming:
        blocks.append(renderer.section(t["upcoming"], upcoming, "📅"))

    day, lessons, ahead = next_school_day(session, now)
    tomorrow_is_weekend = tomorrow.weekday() >= 5
    blocks.append(renderer.school_day(day, lessons, ahead, tomorrow_is_weekend))
    return AccountReport(text="\n\n".join(b for b in blocks if b), announcements=announcements)


def run_digest(settings: Settings,
               session_factory: Callable | None = None,
               send: Callable[[str], object] | None = None,
               now: datetime | None = None) -> list[str]:
    """Fetch every account and send the digest. Returns the messages produced."""
    if session_factory is None:
        from .client import LibrusSession as session_factory  # lazy: needs librus-apix
    now = now or datetime.now()
    renderer = Renderer(settings.language)
    send = send or (lambda text: send_message(settings.telegram_token, settings.chat_ids, text))

    reports: list[str] = []
    announcements: list[Announcement] = []
    seen: set[tuple[str, str]] = set()
    for account in settings.accounts:
        try:
            report = build_account_report(
                session_factory(account.login, account.password), account.name, renderer, now)
            reports.append(report.text)
            for a in report.announcements:  # same school announcements for siblings: show once
                if (a.title, a.date) not in seen:
                    seen.add((a.title, a.date))
                    announcements.append(a)
        except Exception as exc:  # noqa: BLE001
            log.exception("Failed for %s", account.name)
            reports.append(renderer.t["error"].format(
                name=account.name, error=f"{type(exc).__name__}: {exc}"))

    messages = []
    for i, text in enumerate(reports):
        messages.append(f"{renderer.header(now)}\n\n{text}" if i == 0 else text)
    if announcements:
        messages.append(renderer.section(
            renderer.t["announcements"], [renderer.announcement(a) for a in announcements], "📢"))
    for message in messages:
        send(message)
    return messages

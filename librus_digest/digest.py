"""Build and send the daily digest."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as clock, timedelta
from typing import Callable

from .config import Settings
from .models import Announcement, Lesson
from .render import Renderer, esc
from .stats import average_changes
from .telegram import send_message

log = logging.getLogger(__name__)

UPCOMING_DAYS = 10
ACCOUNT_TIMEOUT = 90    # seconds one attempt for one account may take
ACCOUNT_ATTEMPTS = 2    # retries only for timeouts and network errors
MAX_LOOKBACK_DAYS = 7   # how far back a catch-up digest may reach


def report_day(now: datetime, report_after: clock | None) -> datetime:
    """The day a scheduled digest is about.

    With *report_after* (the scheduled time of day), a run that happens earlier is a
    catch-up for the previous weekday - e.g. the PC was off in the evening and boots
    next morning. Without it the digest is always about *now*.
    """
    if report_after is None:
        return now
    day = now if now.time() >= report_after else now - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def first_day_to_report(day: date, last_sent: date | None) -> date:
    """Start of the reporting window: the day after the last delivered digest, so
    that missed days (and weekends) are not lost, at most MAX_LOOKBACK_DAYS back."""
    if last_sent is None or last_sent >= day:
        return day
    return max(last_sent + timedelta(days=1), day - timedelta(days=MAX_LOOKBACK_DAYS - 1))


def _call_with_timeout(func: Callable, timeout: float):
    """Run *func* in a daemon thread and give up after *timeout* seconds.

    The scraper library has no request timeouts, so a stalled Librus connection
    would otherwise block the whole run until the CI job is killed. The abandoned
    thread is a daemon and does not keep the process alive.
    """
    outcome: dict = {}

    def target():
        try:
            outcome["value"] = func()
        except BaseException as exc:  # noqa: BLE001 - re-raised in the caller
            outcome["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise TimeoutError(f"no response from Librus within {timeout:g}s")
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"]


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


def next_school_day(session, now: datetime, horizon: int = UPCOMING_DAYS,
                    include_today: bool = False):
    """First weekday after today (or from today) with lessons: (date, lessons, days_ahead)."""
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    weeks: dict[datetime, list[list[Lesson]]] = {}
    for ahead in range(0 if include_today else 1, horizon + 1):
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


def build_account_report(session, name: str, renderer: Renderer, now: datetime,
                         day: datetime | None = None,
                         since: date | None = None) -> AccountReport:
    """What happened on *day* (default: today) for one student, plus what is coming up.

    *since* widens the window to every date from *since* up to *day*.
    """
    day = day or now
    last = day.strftime("%Y-%m-%d")
    first = (since or day.date()).strftime("%Y-%m-%d")
    catching_up = day.date() < now.date()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = midnight + timedelta(days=1)
    upcoming_from = midnight if catching_up else tomorrow
    horizon = tomorrow + timedelta(days=UPCOMING_DAYS)
    t = renderer.t

    def in_window(value: str) -> bool:
        return first <= value[:10] <= last

    all_grades = session.grades()
    new_grades = [g for g in all_grades if in_window(g.date)]
    absences = [a for a in session.attendance() if in_window(a.date)]
    messages = [m for m in session.messages() if in_window(m.date)]
    announcements = [a for a in _safe("announcements", session.announcements, [])
                     if in_window(a.date)]
    events = _safe("calendar", lambda: session.calendar_events(upcoming_from, horizon), [])
    homework = _safe("homework", lambda: session.homework(upcoming_from, horizon), [])

    def body(href: str) -> str:
        return _safe(f"message {href}", lambda: session.message_body(href), "")

    blocks = [f"<b>{esc(name.upper())}</b>"]
    if not new_grades and not messages:
        blocks.append(t["no_news"])
    if new_grades:
        blocks.append(renderer.section(t["grades"], [renderer.grade(g, show_date=first < last) for g in new_grades], "📝"))
        changes = average_changes(all_grades, new_grades)
        blocks.append(renderer.section(t["average"], [renderer.average_change(c) for c in changes]))
    blocks.append(
        renderer.section(t["attendance"], [renderer.attendance(a) for a in absences], "🚫")
        or f"🚫 <b>{t['attendance']}</b>\n✅ "
           f"{t['attendance_none_past' if catching_up else 'attendance_none']}")
    if messages:
        blocks.append(renderer.section(
            t["messages"], [renderer.message(m, body(m.href)) for m in messages], "✉️"))
    upcoming = renderer.upcoming(events, homework)
    if upcoming:
        blocks.append(renderer.section(t["upcoming"], upcoming, "📅"))

    school_date, lessons, ahead = next_school_day(session, now, include_today=catching_up)
    tomorrow_is_weekend = not catching_up and tomorrow.weekday() >= 5
    blocks.append(renderer.school_day(school_date, lessons, ahead, tomorrow_is_weekend))
    return AccountReport(text="\n\n".join(b for b in blocks if b), announcements=announcements)


def run_digest(settings: Settings,
               session_factory: Callable | None = None,
               send: Callable[[str], object] | None = None,
               now: datetime | None = None,
               account_timeout: float = ACCOUNT_TIMEOUT,
               attempts: int = ACCOUNT_ATTEMPTS,
               retry_pause: float = 5.0,
               report_date: datetime | None = None,
               since: date | None = None) -> list[str]:
    """Fetch every account and send the digest. Returns the messages produced."""
    if session_factory is None:
        from .client import LibrusSession as session_factory  # lazy: needs librus-apix
    now = now or datetime.now()
    day = report_date or now
    renderer = Renderer(settings.language)
    send = send or (lambda text: send_message(settings.telegram_token, settings.chat_ids, text))

    reports: list[str] = []
    announcements: list[Announcement] = []
    seen: set[tuple[str, str]] = set()
    for account in settings.accounts:
        def fetch(account=account):
            return build_account_report(
                session_factory(account.login, account.password), account.name, renderer, now,
                day=day, since=since)

        try:
            for attempt in range(1, attempts + 1):
                try:
                    log.info("Fetching %s (attempt %d/%d)", account.name, attempt, attempts)
                    report = _call_with_timeout(fetch, account_timeout)
                    break
                except (TimeoutError, OSError) as exc:  # transient: try again
                    if attempt == attempts:
                        raise
                    log.warning("%s: %s, retrying", account.name, type(exc).__name__)
                    time.sleep(retry_pause)
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
        messages.append(f"{renderer.header(day, since)}\n\n{text}" if i == 0 else text)
    if announcements:
        messages.append(renderer.section(
            renderer.t["announcements"], [renderer.announcement(a) for a in announcements], "📢"))
    for message in messages:
        send(message)
    return messages

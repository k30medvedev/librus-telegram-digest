"""Command line entry point: ``python -m librus_digest``."""
from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

from . import __version__
from .config import ConfigError, load_dotenv, load_settings
from .digest import first_day_to_report, report_day, run_digest
from .telegram import send_message

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="librus_digest",
        description="Send a daily Librus Synergia digest to Telegram.")
    p.add_argument("--dry-run", action="store_true",
                   help="print the digest to the console instead of sending it")
    p.add_argument("--env-file", default=".env", help="path to a .env file (default: .env)")
    p.add_argument("--once-per-day", action="store_true",
                   help="skip if this day's digest was already delivered (lets a scheduler "
                        "retry safely, e.g. every 20 minutes, without duplicates)")
    p.add_argument("--report-after", metavar="HH:MM",
                   type=lambda v: datetime.strptime(v, "%H:%M").time(),
                   help="the scheduled time: a run earlier than this is a catch-up and "
                        "reports the previous weekday")
    p.add_argument("--log-file", metavar="PATH",
                   help="append the log to this file (for scheduled runs without a console)")
    p.add_argument("--language", help="digest language: en or ru (overrides DIGEST_LANGUAGE)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _use_system_trust_store() -> None:
    """Trust the OS certificate store, not only certifi's bundle.

    Antivirus / corporate proxies that inspect HTTPS install their own root
    certificate in the OS store; without this, requests fails with
    CERTIFICATE_VERIFY_FAILED on such machines.
    """
    try:
        import truststore
    except ImportError:  # optional: certifi is used instead
        return
    truststore.inject_into_ssl()


def _report(message: str, log_file: str | None, error: bool = False) -> None:
    """Tell the user: into the log file if there is one, otherwise to the console."""
    if log_file:
        log.log(logging.ERROR if error else logging.INFO, message)
    else:
        print(message, file=sys.stderr if error else sys.stdout)


def _now() -> datetime:
    return datetime.now()


def _read_marker(marker: Path) -> date | None:
    try:
        return date.fromisoformat(marker.read_text().strip())
    except (OSError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        filename=args.log_file, encoding="utf-8" if args.log_file else None,
                        force=bool(args.log_file))
    load_dotenv(args.env_file)
    _use_system_trust_store()
    socket.setdefaulttimeout(60)  # the scraper's HTTP calls have no timeout of their own
    try:
        settings = load_settings()
    except ConfigError as exc:
        _report(f"Configuration error: {exc}", args.log_file, error=True)
        return 2
    if args.language:
        settings = replace(settings, language=args.language.lower())

    marker = Path(os.environ.get("DIGEST_MARKER", ".digest-last-sent"))
    use_marker = args.once_per_day and not args.dry_run
    now = _now()
    day = report_day(now, args.report_after)
    last_sent = _read_marker(marker) if use_marker else None
    if last_sent and last_sent >= day.date():
        _report(f"Digest for {day:%Y-%m-%d} already delivered, nothing to do.", args.log_file)
        return 0

    failures = 0

    def send(text: str) -> None:
        nonlocal failures
        if args.dry_run:
            print(text, "\n" + "=" * 40)
        else:
            failures += send_message(settings.telegram_token, settings.chat_ids, text)

    if args.dry_run and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        run_digest(settings, send=send, now=now, report_date=day,
                   since=first_day_to_report(day.date(), last_sent))
    except Exception:  # without a console (pythonw) the log is the only trace
        log.exception("Digest failed")
        return 1
    if use_marker and not failures:
        marker.write_text(day.date().isoformat())
    if failures:
        _report(f"{failures} Telegram message(s) could not be delivered", args.log_file,
                error=True)
        return 1  # non-zero exit makes the GitHub Actions run (and cron alerts) visible
    return 0

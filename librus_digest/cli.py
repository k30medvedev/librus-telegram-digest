"""Command line entry point: ``python -m librus_digest``."""
from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

from . import __version__
from .config import ConfigError, load_dotenv, load_settings
from .digest import run_digest
from .telegram import send_message


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="librus_digest",
        description="Send a daily Librus Synergia digest to Telegram.")
    p.add_argument("--dry-run", action="store_true",
                   help="print the digest to the console instead of sending it")
    p.add_argument("--env-file", default=".env", help="path to a .env file (default: .env)")
    p.add_argument("--once-per-day", action="store_true",
                   help="skip if a digest was already delivered today (lets a scheduler "
                        "retry safely, e.g. every 20 minutes, without duplicates)")
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_dotenv(args.env_file)
    _use_system_trust_store()
    socket.setdefaulttimeout(60)  # the scraper's HTTP calls have no timeout of their own
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    if args.language:
        settings = replace(settings, language=args.language.lower())

    marker = Path(os.environ.get("DIGEST_MARKER", ".digest-last-sent"))
    use_marker = args.once_per_day and not args.dry_run
    if use_marker and marker.is_file() and marker.read_text().strip() == date.today().isoformat():
        print("Digest already delivered today, nothing to do.")
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
    run_digest(settings, send=send)
    if use_marker and not failures:
        marker.write_text(date.today().isoformat())
    if failures:
        print(f"{failures} Telegram message(s) could not be delivered", file=sys.stderr)
        return 1  # non-zero exit makes the GitHub Actions run (and cron alerts) visible
    return 0

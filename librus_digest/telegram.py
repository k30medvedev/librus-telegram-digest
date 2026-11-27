"""Minimal Telegram Bot API sender."""
from __future__ import annotations

import logging
import time
from typing import Iterable

import requests

log = logging.getLogger(__name__)

MAX_LEN = 3900  # Telegram's hard limit is 4096; keep some headroom


def split_message(text: str, limit: int = MAX_LEN) -> list[str]:
    """Split *text* into chunks of at most *limit* characters, on line boundaries."""
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:  # a single very long line: hard split
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = ""
        current += line + "\n"
    if current.strip():
        chunks.append(current)
    return [c.rstrip("\n") for c in chunks if c.strip()]


def _post(http, token: str, chat_id: str, chunk: str, attempts: int, pause: float):
    """POST one chunk, retrying on network errors and 429/5xx. Returns the response
    or ``None`` if every attempt failed with a network error."""
    response = None
    for attempt in range(1, attempts + 1):
        try:
            response = http.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": chunk, "parse_mode": "HTML",
                      "disable_web_page_preview": True},
                timeout=30,
            )
            if response.ok or not (response.status_code == 429 or response.status_code >= 500):
                return response
        except requests.RequestException as exc:
            # never log the URL: it contains the bot token
            log.warning("Telegram network error (attempt %d/%d): %s",
                        attempt, attempts, type(exc).__name__)
            response = None
        if attempt < attempts:
            time.sleep(pause * attempt * 4)
    return response


def send_message(token: str, chat_ids: Iterable[str], text: str,
                 session: requests.Session | None = None, pause: float = 0.5,
                 attempts: int = 3) -> int:
    """Send *text* (Telegram HTML) to every chat id. Returns the number of failures.

    A failing chat never prevents delivery to the other chats.
    """
    http = session or requests
    failures = 0
    for chat_id in chat_ids:
        for chunk in split_message(text):
            response = _post(http, token, chat_id, chunk, attempts, pause)
            if response is None or not response.ok:
                failures += 1
                status = ("network error" if response is None
                          else f"{response.status_code}: {response.text}")
                log.error("Telegram delivery failed for chat %s (%s)", chat_id, status)
            time.sleep(pause)
    return failures

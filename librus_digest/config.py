"""Configuration: environment variables, optional ``.env`` file, recipients."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


class ConfigError(Exception):
    """Raised when required settings are missing."""


@dataclass(frozen=True)
class Account:
    name: str
    login: str
    password: str = field(repr=False)  # never print passwords in logs


@dataclass(frozen=True)
class Settings:
    telegram_token: str = field(repr=False)
    chat_ids: tuple[str, ...]
    accounts: tuple[Account, ...]
    language: str = "ru"


def load_dotenv(path: str | Path = ".env", environ: dict | None = None) -> None:
    """Load KEY=VALUE lines from *path* into the environment (existing vars win)."""
    environ = os.environ if environ is None else environ
    path = Path(path)
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        environ.setdefault(key.strip(), value)


def parse_chat_ids(value: str) -> tuple[str, ...]:
    """Split a comma/space/newline separated list of chat ids, dropping duplicates."""
    seen: list[str] = []
    for line in value.splitlines():
        line = line.split("#")[0]  # drop comments first
        for part in line.replace(",", " ").split():
            if part not in seen:
                seen.append(part)
    return tuple(seen)


def load_accounts(environ: Mapping[str, str]) -> tuple[Account, ...]:
    """Read LIBRUS_1_LOGIN / LIBRUS_1_PASSWORD / LIBRUS_1_NAME, LIBRUS_2_..., etc."""
    accounts = []
    i = 1
    while environ.get(f"LIBRUS_{i}_LOGIN"):
        password = environ.get(f"LIBRUS_{i}_PASSWORD", "")
        if not password:
            raise ConfigError(f"LIBRUS_{i}_PASSWORD is missing")
        accounts.append(Account(
            name=environ.get(f"LIBRUS_{i}_NAME") or f"Student {i}",
            login=environ[f"LIBRUS_{i}_LOGIN"],
            password=password,
        ))
        i += 1
    return tuple(accounts)


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    environ = os.environ if environ is None else environ
    token = environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_ids = parse_chat_ids(environ.get("TELEGRAM_CHAT_ID", ""))
    accounts = load_accounts(environ)
    if not accounts:
        raise ConfigError("No Librus accounts: set LIBRUS_1_LOGIN and LIBRUS_1_PASSWORD")
    if not token:
        raise ConfigError("TELEGRAM_BOT_TOKEN is not set")
    if not chat_ids:
        raise ConfigError("TELEGRAM_CHAT_ID is not set")
    return Settings(
        telegram_token=token,
        chat_ids=chat_ids,
        accounts=accounts,
        language=environ.get("DIGEST_LANGUAGE", "ru").strip().lower() or "ru",
    )

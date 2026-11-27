# CLAUDE.md

Guidance for Claude Code (or any coding assistant) working in this repository.

## What this is

A Python bot that logs in to Librus Synergia (a Polish school e-register) and sends a
**daily digest to Telegram**. It is meant to run **on the user's own computer** (Windows
scheduled task, or cron). Full user documentation: `README.md`, beginner guide in Russian:
`README.ru.md`.

## Commands

```bash
pip install -r requirements-dev.txt     # runtime + pytest
python -m pytest                        # all tests, no network needed
python -m librus_digest --dry-run       # real Librus login, prints the digest, sends nothing
python -m librus_digest                 # sends the digest to Telegram
python -m librus_digest --language en   # en | ru (also DIGEST_LANGUAGE env var)
```

Python 3.10+. There is no build step.

## Helping a user get it running (quick setup)

The user does every part that involves secrets. **Never ask for passwords or tokens in
chat, never echo them back, never write them to a tracked file.** `.env` is git-ignored.

Windows: `windows\1-setup.bat` (venv, libraries, `.env`) → user fills `.env` →
`windows\2-test.bat` (preview, sends nothing) → `windows\3-send-now.bat` →
`windows\4-schedule.bat` (scheduled task, default 18:00 Mon–Fri).
Linux/macOS: venv, `pip install -r requirements.txt`, `.env`, `--dry-run`, then cron
(see README).

Telegram chat id: every recipient presses **Start** on the bot, then asks @userinfobot.
Ask before sending real messages or creating a scheduled task on the user's machine.

## Architecture

```
librus_digest/
  client.py    # the ONLY module that imports librus_apix; returns models.* dataclasses
  models.py    # Grade, Attendance, Message, Announcement, Homework, CalendarEvent, Lesson
  stats.py     # grade_value, weighted_average, average_changes (pure)
  render.py    # Renderer(language): data -> Telegram HTML (pure: no network, no clock)
  i18n.py      # STRINGS = {"en": {...}, "ru": {...}}
  digest.py    # build_account_report(), run_digest(): decides what goes in the digest
  telegram.py  # split_message(), send_message() with retries
  config.py    # Settings/Account, .env loading, LIBRUS_N_* parsing
  cli.py       # argparse entry point; exit code 1 if Telegram delivery failed
windows/       # .bat wrappers + PowerShell scripts for non-technical users
tests/         # pytest; Librus is replaced by FakeSession (see tests/test_digest.py)
```

Data flow: `LibrusSession` (client) → models → `digest.build_account_report` (filters to
*today*, adds upcoming events and the next school day) → `Renderer` → `telegram`.

## Conventions

- Keep `render.py`, `stats.py` and `digest.py` free of network access and of
  `librus_apix` imports so they stay testable. All scraper access goes through
  `client.py`; `run_digest` imports it lazily on purpose.
- Output is **Telegram HTML**. Escape every dynamic value with `esc()`; only the tags
  `<b> <i> <blockquote>` are used. Messages are split at 3900 chars by `split_message`.
- New user-visible text goes into **both** languages in `i18n.py`; never hard-code
  strings in `render.py`/`digest.py`.
- Core data (grades, attendance, messages) failing should surface as an error in the
  digest; optional data (announcements, calendar, homework, message bodies, timetable)
  goes through `_safe()` and degrades silently to "nothing".
- Add or change behaviour together with a test; run `python -m pytest` before finishing.
- Never log or print passwords or the Telegram token. `Account.password` is excluded
  from `repr`; `telegram.py` deliberately never logs the request URL.

## Gotchas

- **Scraper, not API.** `librus-apix` parses Librus' HTML and can break when Librus
  changes its pages. Check its releases first, then fix the adapter in `client.py`.
- **Librus drops connections from data-centre addresses** (GitHub runners): DNS resolves,
  TCP never connects. Don't "fix" this with longer timeouts; run from a home connection.
- Opening a message to preview it marks it as read in Librus (also in `--dry-run`).
- A run before the `--report-after` time is a catch-up for the previous weekday. Never
  mark it as today's delivery: that once silently skipped the evening digest.
- The only state is `.digest-last-sent` (the last reported day).
- The scheduled task uses `pythonw.exe`: there is no console, so log through `logging`
  (`--log-file`) rather than relying on `print`.
- `.ps1` files must stay UTF-8 **with BOM** (Windows PowerShell 5.1 reads Cyrillic wrong
  otherwise); `.bat` files stay ASCII with CRLF.
- Antivirus HTTPS inspection breaks certifi-based TLS; `cli.py` injects the OS trust
  store via `truststore`. Don't remove it.
- Do not commit real names, chat ids, tokens or Librus credentials, including in tests
  and fixtures. Use made-up data.

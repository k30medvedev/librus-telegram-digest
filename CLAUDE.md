# CLAUDE.md

Guidance for Claude Code (or any coding assistant) working in this repository.

## What this is

A Python bot that logs in to Librus Synergia (a Polish school e-register) and sends a
**daily digest to Telegram**: today's grades, absences, messages, announcements, what is
coming up and the next school day. Runs locally or on GitHub Actions, triggered by
cron-job.org. Full user documentation: `README.md`.

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

Do these in order; the user does the parts that involve secrets.

1. `pip install -r requirements.txt`
2. `cp .env.example .env` and have the **user** fill in their own Telegram token, chat id
   and Librus login/password. **Never ask for passwords or tokens in chat, never echo
   them back, never put them in a file that is tracked by git.** `.env` is git-ignored.
3. Telegram chat id: the user must press **Start** on their bot first; then read
   `https://api.telegram.org/bot<TOKEN>/getUpdates`.
4. `python -m librus_digest --dry-run` — confirms Librus login and shows the digest.
5. `python -m librus_digest` — confirms Telegram delivery.
6. For daily automatic runs follow "Run it daily on GitHub Actions + cron-job.org" in
   `README.md` (repo secrets/variables, a fine-grained GitHub token with only
   *Actions: Read and write*, a cron-job.org POST to the `workflow_dispatch` endpoint,
   expected response `204`).

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
  changes its pages. If something that worked yesterday fails, check the
  `librus-apix` issues/releases first, then fix the adapter in `client.py`.
- Opening a message to preview it marks it as read in Librus.
- The digest only includes items dated *today*; there is intentionally no persistent
  state (the GitHub Actions runner is stateless).
- GitHub's `schedule:` trigger is unreliable (delays/skips), hence the external
  cron-job.org trigger via `workflow_dispatch`.
- **Librus may drop connections from GitHub-hosted runners** (DNS resolves, TCP connect
  never completes; confirmed with a curl timing step). Symptoms: the Actions run hangs
  and is cancelled. `digest.py` guards every account with a timeout and one retry, but
  the fix is to run the bot from a home connection (Task Scheduler / cron), see
  README "If Librus does not answer GitHub's servers".
- A local antivirus that intercepts HTTPS can cause `CERTIFICATE_VERIFY_FAILED` against
  api.librus.pl; disable it for the run or test in GitHub Actions.
- Do not commit real names, chat ids, tokens or Librus credentials, including in tests
  and fixtures. Use made-up data.

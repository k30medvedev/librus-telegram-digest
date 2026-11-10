# Librus → Telegram digest

A small, dependency-light bot that logs in to **Librus Synergia** (the Polish school
e-register) and sends a clean **daily summary to Telegram**: today's grades, absences,
messages and school announcements, what is coming up (tests, homework, days off) and
when school starts next.

It supports several students at once (siblings get one message each), several Telegram
recipients, and runs for free on **GitHub Actions** triggered by **cron-job.org**.

**Русская версия для новичков: [README.ru.md](README.ru.md)** — пошагово, с нуля.

> **Unofficial project.** Not affiliated with or endorsed by Librus / Synergia. See
> [How it works and legal notes](#how-it-works-and-legal-notes) before using it.

## Sample output

```
Digest · Friday, November 6

ANNA

📝 Grades
🟡 3  Chemistry
      quiz, weight 1
      Chemical bonds - summary
🔵 4  Physics
      homework, weight 1

Average
Chemistry: 4,10 → 4,00
Physics: 3,50 → 3,64

🚫 Absences and lateness
✅ None today

✉️ Messages
Library open
Smith John (teacher), 2026-11-06 08:23
│ Dear students and parents, the library reopens in a new place…

📅 Coming up
Tue 10.11  🔴 Chemistry — test, lesson 6
    covalent, ionic and metallic bonds
Wed 11.11  day off: Independence Day

🏫 School
No school tomorrow.
Next school day — Monday 09.11: from 08:50 to 15:50, 8 lessons
First lesson: #2, Safety at work
```

Colour dots: 🟢 5–6, 🔵 4, 🟡 3, 🔴 1–2, ⚪ non-numeric. Upcoming: 🔴 test / exam,
🟡 quiz.

## Features

- **Grades** of the day with the teacher's comment, plus how the weighted **average**
  changed per subject.
- **Absences and lateness** — the section is always shown, with an explicit
  "None today" when everything is fine.
- **Messages** from the inbox with a preview (first 100 words) and **school announcements**.
- **Coming up**: tests, quizzes, homework and days off for the next 10 days.
- **Next school day**: when it starts, when it ends, how many lessons — skips weekends and holidays.
- Multiple students, multiple Telegram chats, English and Russian UI.
- One broken page (e.g. the calendar) never kills the digest; a failing account is
  reported in the chat while the others still go out.

## Quick start (local)

Requires Python 3.10+.

```bash
git clone https://github.com/k30medvedev/librus-telegram-digest.git
cd librus-telegram-digest
pip install -r requirements.txt

cp .env.example .env        # then edit .env
python -m librus_digest --dry-run   # print the digest instead of sending it
python -m librus_digest             # send it to Telegram
```

### 1. Create the Telegram bot

1. Talk to [@BotFather](https://t.me/BotFather), run `/newbot`, copy the **token**.
2. Open your new bot and press **Start** (every recipient must do this once).
3. Get your chat id: open `https://api.telegram.org/bot<TOKEN>/getUpdates` and look for
   `"chat":{"id": ...}`. Put several ids in `TELEGRAM_CHAT_ID` separated by commas.
   A group or channel works too — add the bot to it and use the (negative) chat id.

### 2. Configuration

All settings are environment variables; a local `.env` file is read automatically.

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | Token from @BotFather |
| `TELEGRAM_CHAT_ID` | yes | One or more chat ids, comma separated |
| `LIBRUS_1_LOGIN`, `LIBRUS_1_PASSWORD` | yes | Synergia login (numeric) and password of the first student |
| `LIBRUS_1_NAME` | no | Display name (default `Student 1`) |
| `LIBRUS_2_*`, `LIBRUS_3_*`, … | no | More students; numbering must have no gaps |
| `DIGEST_LANGUAGE` | no | `en` or `ru` (default `ru`) |

Command line: `--dry-run`, `--language en|ru`, `--env-file PATH`, `--version`.

## Run it daily on GitHub Actions + cron-job.org

No server needed. GitHub Actions runs the bot; [cron-job.org](https://cron-job.org)
(free) tells GitHub *when* to run it.

> **Why not GitHub's own `schedule:`?** Scheduled workflows are best-effort: runs are
> frequently delayed by hours or skipped entirely, and in public repositories they are
> disabled after 60 days without repository activity. An external scheduler calling the
> `workflow_dispatch` API is precise, and it is not affected by that 60-day rule.
>
> What *can* stop it: the GitHub token you give the scheduler expires (renew it before
> the date you set), or the token / workflow is deleted.

### 1. Put the project in your own repository

Fork this repo (or push it to a **private** repository of your own — the digest contains
your children's data, so keep the repo private if you can).

### 2. Add secrets and variables

Repository → **Settings → Secrets and variables → Actions**.

*Secrets*: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `LIBRUS_1_LOGIN`, `LIBRUS_1_PASSWORD`
(and `LIBRUS_2_*` … up to 5 students).

*Variables* (optional): `LIBRUS_1_NAME`, `LIBRUS_2_NAME`, …, `DIGEST_LANGUAGE`
(`en`/`ru`), `DIGEST_TIMEZONE` (default `Europe/Warsaw`).

Open **Actions → Librus digest → Run workflow** once to check that a digest arrives.

### 3. Create a minimal GitHub token for the scheduler

GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained tokens
→ Generate new token**:

- **Repository access**: *Only select repositories* → this repository.
- **Repository permissions**: **Actions: Read and write** — nothing else.
- Set an expiration (you will have to renew the token when it expires).

Copy the token; it is shown once. Treat it like a password and never paste it into chats
or commit it.

### 4. Create the cron job on cron-job.org

Create a cronjob with:

| Field | Value |
|---|---|
| URL | `https://api.github.com/repos/<owner>/<repo>/actions/workflows/digest.yml/dispatches` |
| Schedule | custom crontab `0 19 * * 1-5` (19:00, Monday–Friday) |
| Time zone (Advanced) | your local zone, e.g. `Europe/Warsaw` |
| Request method | `POST` |
| Headers | `Authorization: Bearer <your token>` · `Accept: application/vnd.github+json` · `User-Agent: cronjob` · `Content-Type: application/json` |
| Request body | `{"ref":"main"}` |

Use **Test run**: GitHub answers **`204 No Content`** and a `workflow_dispatch` run
appears in the Actions tab. `401/403` means a token problem, `404` a wrong URL or
repository. Enable failure notifications on the cron-job.org *Notifications* tab.

The same call from a shell, for debugging:

```bash
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/<owner>/<repo>/actions/workflows/digest.yml/dispatches \
  -d '{"ref":"main"}'
```

### If Librus does not answer GitHub's servers

Librus sometimes drops connections from GitHub's data-centre IP addresses: DNS works but
the TCP connection never completes, the run hangs and is cancelled after the job
timeout (the bot now aborts after 90 s per account, retries once and reports the error
in the chat). This is outside the bot's control and can come and go.

If it happens, run the bot from a machine on a normal home connection instead. On
Windows, a scheduled task does the job (adjust the paths, and use your own Python):

```powershell
$a = New-ScheduledTaskAction -Execute "cmd.exe" -WorkingDirectory "C:\path\to\librus-telegram-digest" `
  -Argument '/c "set PYTHONUTF8=1&& python -m librus_digest >> librus-digest.log 2>&1"'
$t = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 19:00
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName LibrusDigest -Action $a -Trigger $t -Settings $s
```

On Linux/macOS use cron: `0 19 * * 1-5 cd /path/to/repo && python -m librus_digest`.
The local setup reads the same settings from a `.env` file (see `.env.example`). Turn
the cron-job.org job off while you run it locally, otherwise you get duplicates.

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest
```

```
librus_digest/
  client.py    # the ONLY module that talks to Librus (adapter over librus-apix)
  models.py    # plain dataclasses: Grade, Attendance, Message, ...
  stats.py     # weighted averages
  render.py    # data -> Telegram HTML (pure, no network, no clock)
  i18n.py      # UI strings (en, ru) — add a language here
  digest.py    # orchestration: what goes into the digest
  telegram.py  # message splitting and sending
  config.py    # env / .env / recipients
  cli.py       # python -m librus_digest
tests/         # pytest, no network: Librus is replaced by a fake session
```

The scraper is isolated behind `LibrusSession`, so everything else is tested against a
fake. If Librus changes its pages and `librus-apix` breaks, only `client.py` needs to
change.

To add a language, copy the `en` block in `i18n.py`.

## How it works and legal notes

**This is a scraper, not an API client.** Librus offers no public API for parents and
students. The bot uses [`librus-apix`](https://github.com/poroknights/librus-apix) (MIT),
an unofficial library that logs in with your own credentials and parses the same web
pages you see in the browser. Consequences:

- It can **break without notice** whenever Librus changes its pages or login flow.
- Librus' terms of service may restrict automated access. **Read the terms that apply to
  your school/account yourself** — this README is not legal advice and the authors have
  not verified them.
- Be a good citizen: the bot logs in **once per run, once a day**, and only reads data.
  It never writes, sends or changes anything in Librus. Don't schedule it aggressively.

**Privacy.**

- Use it only for **your own account or your own children's** accounts. Don't run it as a
  service that stores other people's Librus passwords.
- Grades, absences and messages of minors are personal data. The digest is sent through
  Telegram (a third-party cloud service) to the chats you configure — keep the recipient
  list tight and the repository private.
- Credentials live in environment variables / GitHub secrets only. They are never logged
  (passwords are excluded from object representations, the Telegram token is not written
  to logs), and `.env` is git-ignored.

**Known behaviour to be aware of.**

- Opening a message to preview it **marks it as read** in Librus.
- The digest shows items **dated today**; something a teacher enters late for an earlier
  date will not appear. Absences only show up once a teacher has recorded them.
- Subject names, comments and messages stay in their original language (Polish).
- The weighted average is computed by the bot (`+` = +0.5, `−` = −0.25) and may differ
  slightly from the school's official calculation.

## Credits

- [librus-apix](https://github.com/poroknights/librus-apix) — the scraping library doing
  the heavy lifting (MIT).

## License

[MIT](LICENSE)

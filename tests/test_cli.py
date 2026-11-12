import pytest

from librus_digest import cli

ENV = {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "1",
       "LIBRUS_1_LOGIN": "100", "LIBRUS_1_PASSWORD": "pw"}


@pytest.fixture
def run(tmp_path, monkeypatch):
    """Run cli.main() in a temp dir with Librus and Telegram stubbed out."""
    monkeypatch.chdir(tmp_path)
    for key in list(ENV) + ["DIGEST_MARKER"]:
        monkeypatch.delenv(key, raising=False)
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    state = {"digests": 0, "delivery_failures": 0}

    def fake_run_digest(settings, send=None, **kwargs):
        state["digests"] += 1
        send("digest")

    monkeypatch.setattr(cli, "run_digest", fake_run_digest)
    monkeypatch.setattr(cli, "send_message", lambda *a, **k: state["delivery_failures"])

    def call(*argv):
        return cli.main(["--env-file", str(tmp_path / "none.env"), *argv])

    call.state, call.dir = state, tmp_path
    return call


def test_once_per_day_sends_only_once(run):
    assert run("--once-per-day") == 0 and run.state["digests"] == 1
    assert run("--once-per-day") == 0 and run.state["digests"] == 1     # skipped
    assert (run.dir / ".digest-last-sent").exists()


def test_once_per_day_is_not_marked_when_delivery_fails(run):
    run.state["delivery_failures"] = 1
    assert run("--once-per-day") == 1
    assert not (run.dir / ".digest-last-sent").exists()
    run.state["delivery_failures"] = 0
    assert run("--once-per-day") == 0 and run.state["digests"] == 2       # retried


def test_stale_marker_from_another_day_does_not_block(run):
    (run.dir / ".digest-last-sent").write_text("2000-01-01")
    run("--once-per-day")
    assert run.state["digests"] == 1


def test_without_flag_always_sends_and_dry_run_ignores_marker(run):
    run()
    run()
    assert run.state["digests"] == 2 and not (run.dir / ".digest-last-sent").exists()
    run("--once-per-day")
    run("--once-per-day", "--dry-run")                                    # dry run ignores marker
    assert run.state["digests"] == 4


def test_missing_configuration_returns_2(run, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN")
    assert run() == 2

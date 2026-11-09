import pytest

from librus_digest.config import (ConfigError, load_accounts, load_dotenv,
                                  load_settings, parse_chat_ids)

BASE = {
    "TELEGRAM_BOT_TOKEN": "123:abc",
    "TELEGRAM_CHAT_ID": "1",
    "LIBRUS_1_LOGIN": "100",
    "LIBRUS_1_PASSWORD": "pw",
}


def test_parse_chat_ids_handles_separators_comments_and_duplicates():
    assert parse_chat_ids("1, 2,2\n3 # me\n\n") == ("1", "2", "3")
    assert parse_chat_ids("") == ()


def test_load_accounts_reads_numbered_accounts_until_gap():
    env = {**BASE, "LIBRUS_1_NAME": "Anna",
           "LIBRUS_2_LOGIN": "200", "LIBRUS_2_PASSWORD": "p2",
           "LIBRUS_4_LOGIN": "400", "LIBRUS_4_PASSWORD": "p4"}   # gap at 3 -> ignored
    accounts = load_accounts(env)
    assert [(a.name, a.login) for a in accounts] == [("Anna", "100"), ("Student 2", "200")]


def test_password_is_not_in_repr():
    (account,) = load_accounts(BASE)
    assert "pw" not in repr(account)


def test_missing_password_is_an_error():
    with pytest.raises(ConfigError, match="LIBRUS_1_PASSWORD"):
        load_accounts({"LIBRUS_1_LOGIN": "100"})


@pytest.mark.parametrize("missing", ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "LIBRUS_1_LOGIN"])
def test_load_settings_requires_core_values(missing):
    env = {k: v for k, v in BASE.items() if k != missing}
    with pytest.raises(ConfigError):
        load_settings(env)


def test_load_settings_ok_and_language_default():
    settings = load_settings(BASE)
    assert settings.chat_ids == ("1",) and settings.language == "ru"
    assert load_settings({**BASE, "DIGEST_LANGUAGE": " EN "}).language == "en"


def test_load_dotenv_does_not_override_existing(tmp_path):
    f = tmp_path / ".env"
    f.write_text('# comment\nA=1\nB="two words"\nC=\'x\'\nA=ignored\nbadline\n', encoding="utf-8")
    env = {"A": "keep"}
    load_dotenv(f, env)
    assert env == {"A": "keep", "B": "two words", "C": "x"}


def test_load_dotenv_missing_file_is_fine(tmp_path):
    env = {}
    load_dotenv(tmp_path / "nope.env", env)
    assert env == {}

from librus_digest.telegram import MAX_LEN, send_message, split_message


def test_short_text_is_one_chunk():
    assert split_message("hello\nworld") == ["hello\nworld"]


def test_long_text_splits_on_line_boundaries_within_limit():
    lines = [f"line {i} " + "x" * 50 for i in range(200)]
    chunks = split_message("\n".join(lines), limit=500)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)
    assert "\n".join(chunks).split("\n") == lines          # nothing lost or reordered


def test_single_overlong_line_is_hard_split():
    chunks = split_message("y" * (MAX_LEN * 2 + 10))
    assert all(len(c) <= MAX_LEN for c in chunks)
    assert "".join(chunks) == "y" * (MAX_LEN * 2 + 10)


def test_empty_text_sends_nothing():
    assert split_message("  \n ") == []


class FakeResponse:
    def __init__(self, ok=True, status_code=200, text=""):
        self.ok, self.status_code, self.text = ok, status_code, text


class FakeSession:
    def __init__(self, fail_for=()):
        self.calls, self.fail_for = [], set(fail_for)

    def post(self, url, json, timeout):
        self.calls.append((url, json))
        return FakeResponse(ok=json["chat_id"] not in self.fail_for, status_code=400, text="boom")


def test_send_message_posts_to_every_chat_with_html():
    session = FakeSession()
    failures = send_message("TOKEN", ["1", "2"], "hi", session=session, pause=0)
    assert failures == 0
    assert [c[1]["chat_id"] for c in session.calls] == ["1", "2"]
    assert all(c[1]["parse_mode"] == "HTML" for c in session.calls)
    assert session.calls[0][0] == "https://api.telegram.org/botTOKEN/sendMessage"


def test_send_message_counts_failures_and_never_logs_token(caplog):
    session = FakeSession(fail_for={"2"})
    with caplog.at_level("ERROR"):
        failures = send_message("SECRET-TOKEN", ["1", "2"], "hi", session=session, pause=0)
    assert failures == 1
    assert "SECRET-TOKEN" not in caplog.text


class FlakySession:
    """Fails with a network error N times, then succeeds."""

    def __init__(self, failures_before_success):
        self.left, self.calls = failures_before_success, 0

    def post(self, url, json, timeout):
        import requests
        self.calls += 1
        if self.left > 0:
            self.left -= 1
            raise requests.ReadTimeout("slow")
        return FakeResponse()


def test_network_error_is_retried_then_succeeds():
    session = FlakySession(failures_before_success=2)
    assert send_message("T", ["1"], "hi", session=session, pause=0) == 0
    assert session.calls == 3


def test_persistent_network_error_is_counted_not_raised(caplog):
    session = FlakySession(failures_before_success=99)
    with caplog.at_level("WARNING"):
        failures = send_message("SECRET-TOKEN", ["1", "2"], "hi", session=session, pause=0)
    assert failures == 2                     # one per chat; the second chat was still tried
    assert session.calls == 6                # 3 attempts per chat
    assert "SECRET-TOKEN" not in caplog.text


def test_server_errors_are_retried():
    class Server500Once:
        calls = 0

        def post(self, url, json, timeout):
            self.calls += 1
            return FakeResponse(ok=self.calls > 1, status_code=502, text="bad gateway")

    session = Server500Once()
    assert send_message("T", ["1"], "hi", session=session, pause=0) == 0
    assert session.calls == 2

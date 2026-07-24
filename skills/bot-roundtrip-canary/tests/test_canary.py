"""Tests for the bot round-trip canary core logic.

Uses fake transports + injected clock/sleep so runs are deterministic and instant.
Proves: pass when the tag echoes back, fail (with alert) on no-echo timeout, on a
wedged poll (raises), and on send failure. Also proves the deadline is honored.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import canary as C  # noqa: E402


class FakeClock:
    """Monotonic clock that only advances when `sleep` is called."""

    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, secs):
        self.t += secs


class EchoAfter:
    """Reflects the sent text back after `after` polls (simulates a healthy path)."""

    def __init__(self, after=1):
        self.after = after
        self.sent = None
        self.polls = 0

    def send(self, text):
        self.sent = text

    def poll(self):
        self.polls += 1
        if self.sent is not None and self.polls >= self.after:
            return [self.sent, "unrelated chatter"]
        return ["unrelated chatter"]


class NeverEcho:
    """Send succeeds; receive path never returns the tag (silent wedge)."""

    def send(self, text):
        self.sent = text

    def poll(self):
        return ["noise", "more noise"]


class WedgedPoll:
    """Receive path raises on every poll (ConnectTimeout-style hang)."""

    def send(self, text):
        pass

    def poll(self):
        raise TimeoutError("connect timeout")


class SendBroken:
    def send(self, text):
        raise ConnectionError("bot send path down")

    def poll(self):
        return []


def _run(transport, **kw):
    clk = FakeClock()
    return C.run_canary(
        transport, tag="SKCANARY-test-1", timeout=kw.pop("timeout", 10.0),
        poll_interval=kw.pop("poll_interval", 2.0), now=clk.now, sleep=clk.sleep, **kw,
    )


# ---- pass-after -------------------------------------------------------------
def test_echo_returns_ok():
    r = _run(EchoAfter(after=1))
    assert r.ok is True
    assert r.reason == "echo-received"
    assert r.tag == "SKCANARY-test-1"
    assert r.latency_s is not None


def test_echo_after_a_few_polls_still_ok():
    r = _run(EchoAfter(after=3), poll_interval=1.0, timeout=30.0)
    assert r.ok is True
    assert r.polls == 3


def test_tag_must_match_exactly():
    class WrongTag:
        def send(self, text):
            pass

        def poll(self):
            return ["SKCANARY-different-tag echoed"]

    r = _run(WrongTag())
    assert r.ok is False
    assert r.reason == "no-echo-timeout"


# ---- fail-before ------------------------------------------------------------
def test_no_echo_times_out():
    r = _run(NeverEcho(), timeout=10.0, poll_interval=2.0)
    assert r.ok is False
    assert r.reason == "no-echo-timeout"
    assert r.error == ""


def test_wedged_poll_reports_error_and_times_out():
    r = _run(WedgedPoll(), timeout=6.0, poll_interval=2.0)
    assert r.ok is False
    assert r.reason == "poll-error-timeout"
    assert "TimeoutError" in r.error


def test_send_failure_fails_fast():
    r = _run(SendBroken())
    assert r.ok is False
    assert r.reason == "send-failed"
    assert "ConnectionError" in r.error


def test_deadline_is_honored():
    """A never-echoing transport must not loop forever; clock passes the deadline."""
    clk = FakeClock()
    r = C.run_canary(NeverEcho(), tag="t", timeout=8.0, poll_interval=2.0,
                     now=clk.now, sleep=clk.sleep)
    assert r.ok is False
    assert clk.now() >= 8.0


# ---- alert wiring -----------------------------------------------------------
def test_emit_alert_builds_expected_command():
    captured = {}

    def fake_runner(argv):
        captured["argv"] = argv
        return 0

    rc = C.emit_alert("boom", level="crit", key="k1", ttl=99, runner=fake_runner)
    assert rc == 0
    assert captured["argv"] == ["sk-alert", "-l", "crit", "-k", "k1", "-t", "99", "boom"]


# ---- tag helper -------------------------------------------------------------
def test_make_tag_is_unique_and_prefixed():
    a, b = C.make_tag("X"), C.make_tag("X")
    assert a != b
    assert a.startswith("X-")


# ---- token loader (no token in code) ---------------------------------------
def test_token_loader_reads_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    assert C._load_bot_token() == "123:abc"


def test_transport_refuses_without_token(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("SKALERT_ENV_FILE", str(tmp_path / "nope.env"))
    with pytest.raises(RuntimeError):
        C.TelegramBotTransport(chat_id="1")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

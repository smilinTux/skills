#!/usr/bin/env python3
"""bot-roundtrip-canary — synthetic probe for the fleet's bot / comms round-trip.

Sends a uniquely-tagged message through a bot/comms *send* path, then watches the
*receive* path for the same tag to come back within a deadline. If the tag does not
return in time (silent wedge, ConnectTimeout hang, dead receive-tree), the canary
exits non-zero and emits an alert via `sk-alert`.

Design:
  - The round-trip logic (`run_canary`) is transport-agnostic and depends only on a
    small `Transport` seam: `send(text)` + `poll() -> list[str]`. That makes it
    unit-testable with a fake transport and reusable for Telegram, skcomms, skchat,
    or any bridge inbox.
  - `TelegramBotTransport` is the reference concrete transport (Bot API, stdlib
    urllib only). It NEVER hardcodes a token: it reads `TELEGRAM_BOT_TOKEN` from the
    environment, falling back to the Hermes env file the rest of the fleet uses.

No third-party dependencies. Python 3.8+.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Protocol


# --------------------------------------------------------------------------- #
# Transport seam
# --------------------------------------------------------------------------- #
class Transport(Protocol):
    """Minimal contract the canary needs from any bot/comms path."""

    def send(self, text: str) -> None:
        """Push `text` onto the send path. Raise on failure."""
        ...

    def poll(self) -> List[str]:
        """Return message texts newly seen on the receive path. May raise."""
        ...


# --------------------------------------------------------------------------- #
# Result
# --------------------------------------------------------------------------- #
@dataclass
class CanaryResult:
    ok: bool
    tag: str
    latency_s: Optional[float] = None
    polls: int = 0
    reason: str = ""
    error: str = ""

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "tag": self.tag,
            "latency_s": self.latency_s,
            "polls": self.polls,
            "reason": self.reason,
            "error": self.error,
        }


def make_tag(prefix: str = "SKCANARY") -> str:
    """A tag unlikely to collide and easy to grep in logs."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}-{int(time.time())}"


# --------------------------------------------------------------------------- #
# Core round-trip logic (pure; time + transport injected for testing)
# --------------------------------------------------------------------------- #
def run_canary(
    transport: Transport,
    tag: Optional[str] = None,
    timeout: float = 30.0,
    poll_interval: float = 2.0,
    *,
    message_template: str = "{tag} :: bot round-trip canary, please ignore",
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    log: Optional[Callable[[str], None]] = None,
) -> CanaryResult:
    """Send a tagged probe and wait for it to echo back on the receive path.

    Returns a CanaryResult. `ok=True` only if the exact tag is observed on `poll()`
    before `timeout` elapses. A send failure, or the deadline passing without the
    tag, yields `ok=False` with a `reason`.
    """
    tag = tag or make_tag()
    _log = log or (lambda _m: None)
    text = message_template.format(tag=tag)

    # 1. Send. A send failure is an immediate, unambiguous canary failure.
    try:
        transport.send(text)
        _log(f"sent tag={tag}")
    except Exception as exc:  # noqa: BLE001 - transport can raise anything
        return CanaryResult(
            ok=False, tag=tag, reason="send-failed", error=f"{type(exc).__name__}: {exc}"
        )

    # 2. Poll the receive path until the tag returns or the deadline passes.
    start = now()
    deadline = start + timeout
    polls = 0
    last_error = ""
    while True:
        try:
            for msg in transport.poll():
                if tag in msg:
                    latency = now() - start
                    _log(f"echo seen tag={tag} latency={latency:.2f}s polls={polls + 1}")
                    return CanaryResult(
                        ok=True, tag=tag, latency_s=round(latency, 3), polls=polls + 1,
                        reason="echo-received",
                    )
            polls += 1
        except Exception as exc:  # noqa: BLE001
            # A poll error (e.g. ConnectTimeout wedge) is exactly what we hunt for.
            # Record it but keep trying until the deadline so transients self-heal.
            last_error = f"{type(exc).__name__}: {exc}"
            _log(f"poll error: {last_error}")

        if now() >= deadline:
            reason = "poll-error-timeout" if last_error else "no-echo-timeout"
            return CanaryResult(
                ok=False, tag=tag, polls=polls, reason=reason, error=last_error,
            )
        # Do not overshoot the deadline while sleeping.
        remaining = deadline - now()
        sleep(min(poll_interval, remaining) if remaining > 0 else 0)


# --------------------------------------------------------------------------- #
# Alerting (shells to the fleet's sk-alert primitive; injectable for tests)
# --------------------------------------------------------------------------- #
def emit_alert(
    message: str,
    *,
    level: str = "crit",
    key: str = "bot-roundtrip-canary",
    ttl: int = 3600,
    runner: Callable[[List[str]], int] = None,
) -> int:
    """Fire an alert via `sk-alert`. Returns the alerter's exit code (0 = sent)."""
    cmd = ["sk-alert", "-l", level, "-k", key, "-t", str(ttl), message]

    def _default_runner(argv: List[str]) -> int:
        try:
            return subprocess.run(argv, check=False).returncode
        except FileNotFoundError:
            sys.stderr.write("emit_alert: sk-alert not on PATH; alert dropped\n")
            return 127

    return (runner or _default_runner)(cmd)


# --------------------------------------------------------------------------- #
# Reference transport: Telegram Bot API (stdlib only, no token in code)
# --------------------------------------------------------------------------- #
def _load_bot_token() -> Optional[str]:
    """Token from env, else from the Hermes env file the fleet already uses."""
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    if tok:
        return tok
    env_file = os.environ.get(
        "SKALERT_ENV_FILE", os.path.expanduser("~/.hermes/.env")
    )
    try:
        with open(env_file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val
    except OSError:
        pass
    return None


@dataclass
class TelegramBotTransport:
    """Send via sendMessage; receive by scanning getUpdates for the tag.

    Note on semantics: a bot does not receive its own outgoing sendMessage via
    getUpdates. This transport verifies the round-trip when a chat member or an
    echo bridge reflects the tagged message back into the update stream (the exact
    receive path that wedges). For a pure self-echo you would point `poll()` at the
    bridge inbox instead; the `Transport` seam makes that a drop-in swap.
    """

    chat_id: str
    token: str = field(default_factory=lambda: _load_bot_token() or "")
    api_base: str = "https://api.telegram.org"
    http_timeout: float = 10.0
    _offset: int = 0

    def __post_init__(self) -> None:
        if not self.token:
            raise RuntimeError(
                "no TELEGRAM_BOT_TOKEN in env or Hermes env file; refusing to run"
            )

    def _url(self, method: str) -> str:
        return f"{self.api_base}/bot{self.token}/{method}"

    def _get(self, method: str, params: dict) -> dict:
        url = self._url(method) + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=self.http_timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post(self, method: str, params: dict) -> dict:
        data = urllib.parse.urlencode(params).encode("utf-8")
        req = urllib.request.Request(self._url(method), data=data)
        with urllib.request.urlopen(req, timeout=self.http_timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def send(self, text: str) -> None:
        res = self._post("sendMessage", {"chat_id": self.chat_id, "text": text})
        if not res.get("ok"):
            raise RuntimeError(f"sendMessage failed: {res}")

    def poll(self) -> List[str]:
        res = self._get("getUpdates", {"offset": self._offset, "timeout": 0})
        if not res.get("ok"):
            raise RuntimeError(f"getUpdates failed: {res}")
        texts: List[str] = []
        for upd in res.get("result", []):
            self._offset = max(self._offset, upd.get("update_id", 0) + 1)
            for key in ("message", "edited_message", "channel_post"):
                m = upd.get(key)
                if not m:
                    continue
                for field_name in ("text", "caption"):
                    if m.get(field_name):
                        texts.append(m[field_name])
        return texts


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bot-roundtrip-canary",
        description="Synthetic bot/comms round-trip probe. Exits non-zero + alerts on failure.",
    )
    p.add_argument(
        "--chat-id",
        default=os.environ.get("SKCANARY_CHAT_ID") or os.environ.get("SKALERT_CHAT_ID"),
        help="Target chat id (env SKCANARY_CHAT_ID / SKALERT_CHAT_ID).",
    )
    p.add_argument("--timeout", type=float,
                   default=float(os.environ.get("SKCANARY_TIMEOUT", "30")),
                   help="Deadline in seconds for the echo to return (default 30).")
    p.add_argument("--poll-interval", type=float,
                   default=float(os.environ.get("SKCANARY_POLL_INTERVAL", "2")),
                   help="Seconds between receive-path polls (default 2).")
    p.add_argument("--tag-prefix", default=os.environ.get("SKCANARY_TAG_PREFIX", "SKCANARY"),
                   help="Prefix for the unique probe tag (default SKCANARY).")
    p.add_argument("--no-alert", action="store_true",
                   help="Do not fire sk-alert on failure (still exits non-zero).")
    p.add_argument("--alert-key", default="bot-roundtrip-canary",
                   help="sk-alert de-dup key (default bot-roundtrip-canary).")
    p.add_argument("--alert-ttl", type=int, default=3600,
                   help="sk-alert de-dup TTL seconds (default 3600).")
    p.add_argument("--json", action="store_true", help="Emit the result as JSON on stdout.")
    p.add_argument("--verbose", action="store_true", help="Log progress to stderr.")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.chat_id:
        sys.stderr.write("error: no chat id (--chat-id / SKCANARY_CHAT_ID / SKALERT_CHAT_ID)\n")
        return 2

    logger = (lambda m: sys.stderr.write(f"[canary] {m}\n")) if args.verbose else None

    try:
        transport = TelegramBotTransport(chat_id=str(args.chat_id))
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"error: cannot build transport: {exc}\n")
        return 2

    result = run_canary(
        transport,
        tag=make_tag(args.tag_prefix),
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        log=logger,
    )

    if args.json:
        print(json.dumps(result.as_dict()))
    else:
        status = "OK" if result.ok else "FAIL"
        detail = (f"latency={result.latency_s}s" if result.ok
                  else f"reason={result.reason} err={result.error}")
        print(f"canary {status} tag={result.tag} {detail}")

    if not result.ok and not args.no_alert:
        emit_alert(
            f"Bot round-trip canary FAILED: {result.reason} "
            f"(tag {result.tag}; {result.error or 'no echo within deadline'})",
            key=args.alert_key,
            ttl=args.alert_ttl,
        )

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

---
name: bot-roundtrip-canary
description: Use to run or wire up a synthetic bot/comms round-trip probe. Sends a uniquely-tagged message through the fleet's bot send path and confirms the same tag returns on the receive path within a deadline, exiting non-zero and firing sk-alert if the round-trip is broken. Catches silent wedges (Telegram bridge ConnectTimeout hangs, dead receive-tree bugs).
---

# bot-roundtrip-canary

A **round-trip canary**: a periodic synthetic probe that sends a tagged test message
through a bot / comms path and verifies it comes back within a timeout. If the tag
does not return in time, the canary exits non-zero and fires an alert. This is the
early-warning for silent wedges that health checks miss, e.g. the Telegram bridge
poller hanging on a `ConnectTimeout`, or a receive-path "dead tree" that stops
delivering while the process still looks alive.

## When to use

- You want a heartbeat that proves the bot pipeline is *actually flowing end to end*,
  not just that a process is up.
- You are wiring monitoring for the Telegram bots (`@seaBird_Lumi_bot`, DR group bot,
  SKAlert) or another comms transport, and need a break-glass alert.
- Something delivered late/never and you want to reproduce the round-trip on demand.

## What it does

1. Generates a unique tag (`SKCANARY-<rand>-<epoch>`).
2. Sends `"<tag> :: bot round-trip canary..."` on the **send** path.
3. Polls the **receive** path until the tag returns or the deadline passes.
4. On success: exits `0` (reports latency). On timeout / send failure / wedged poll:
   exits `1` and fires `sk-alert -l crit` (de-duped).

The round-trip logic (`run_canary`) is transport-agnostic; it depends only on a small
`Transport` seam (`send(text)` + `poll() -> list[str]`). `TelegramBotTransport` is the
reference concrete transport (stdlib `urllib`, no dependencies). Point `poll()` at a
different receive path (bridge inbox, skcomms, skchat) to canary that path instead.

## Configuration (env or flags, never hardcode secrets)

| Setting | Env | Flag | Default |
|---|---|---|---|
| Target chat | `SKCANARY_CHAT_ID` / `SKALERT_CHAT_ID` | `--chat-id` | (required) |
| Deadline (s) | `SKCANARY_TIMEOUT` | `--timeout` | 30 |
| Poll interval (s) | `SKCANARY_POLL_INTERVAL` | `--poll-interval` | 2 |
| Tag prefix | `SKCANARY_TAG_PREFIX` | `--tag-prefix` | SKCANARY |
| Bot token | `TELEGRAM_BOT_TOKEN` (else `~/.hermes/.env`) | (none) | (required) |

The token is read from the environment or the Hermes env file the rest of the fleet
already uses (`SKALERT_ENV_FILE`, default `~/.hermes/.env`). It is **never** stored in
this skill. `--no-alert` runs the probe without firing sk-alert (still exits non-zero).

## Run

```bash
python3 canary.py --chat-id "$SKALERT_CHAT_ID" --timeout 30 --verbose
python3 canary.py --json            # machine-readable result on stdout
```

Exit codes: `0` round-trip OK, `1` round-trip failed (alert fired), `2` misconfig.

## Important semantics (Telegram)

A bot does **not** receive its own outgoing `sendMessage` back through `getUpdates`.
`TelegramBotTransport` verifies the round-trip when a chat member or an echo bridge
reflects the tagged message into the update stream (the same receive path that wedges).
For a pure self-echo, implement `Transport.poll()` against your bridge's inbox / message
log and pass that transport instead. The seam makes it a one-line swap.

## Wiring to a scheduler (document only; do NOT auto-install)

**systemd user timer** (per-agent, matches the `skwhisper@` pattern):

```ini
# ~/.config/systemd/user/bot-roundtrip-canary.service
[Unit]
Description=Bot round-trip canary probe
[Service]
Type=oneshot
Environment=SKCANARY_CHAT_ID=%I
ExecStart=%h/clawd/skskills/skills/bot-roundtrip-canary/canary.py --timeout 45
```
```ini
# ~/.config/systemd/user/bot-roundtrip-canary.timer
[Unit]
Description=Run bot round-trip canary every 15 min
[Timer]
OnBootSec=5min
OnUnitActiveSec=15min
[Install]
WantedBy=timers.target
```
Enable: `systemctl --user enable --now bot-roundtrip-canary.timer`

**cron** alternative:

```cron
*/15 * * * * TELEGRAM_BOT_TOKEN=... SKCANARY_CHAT_ID=... /usr/bin/python3 \
  ~/clawd/skskills/skills/bot-roundtrip-canary/canary.py --timeout 45 >>~/.skcapstone/agents/lumina/logs/canary.log 2>&1
```

The canary self-alerts on failure via `sk-alert` (crit, de-duped 1h), so the scheduler
only needs to run it. Alerting is de-duplicated so a sustained outage pings once per hour.

## Tests

```bash
python3 -m pytest tests/ -q
```

Fake transports + injected clock prove: pass on echo, fail on no-echo timeout, fail on a
wedged (raising) poll, fail on send failure, deadline honored, and the sk-alert command
shape. No network required.

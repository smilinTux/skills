"""Outbound safety gate: scan emitted artifacts for secrets & private endpoints."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from skskills.plugin.models import PluginSpec

# (kind, compiled regex). Order matters only for reporting.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("secret", re.compile(r"ghp_[A-Za-z0-9]{36}")),
    ("secret", re.compile(r"github_pat_[A-Za-z0-9_]{22,}")),
    ("secret", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("secret", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("secret", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("private-endpoint", re.compile(r"\b127\.0\.0\.1\b")),
    ("private-endpoint", re.compile(r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
    ("private-endpoint", re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b")),
    (
        "private-endpoint",
        re.compile(r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b"),
    ),
    ("private-endpoint", re.compile(r"\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b")),
    ("private-endpoint", re.compile(r"[A-Za-z0-9-]+\.ts\.net\b")),
]


@dataclass
class ScrubFinding:
    file: Path
    line: int
    kind: str
    snippet: str


def scan_dir(out_dir: Path) -> list[ScrubFinding]:
    """Walk all files under out_dir and return pattern matches."""
    findings: list[ScrubFinding] = []
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for kind, pat in _PATTERNS:
                m = pat.search(line)
                if m:
                    findings.append(
                        ScrubFinding(file=path, line=lineno, kind=kind, snippet=m.group(0))
                    )
    return findings


def gate_publish(spec: PluginSpec, out_dir: Path, confirmed: bool) -> tuple[bool, list[str]]:
    """Three-gate publish check: publish flag + confirmation + clean scan."""
    reasons: list[str] = []
    if not spec.publish:
        reasons.append(f"plugin '{spec.name}' is not marked `publish: true` in catalog.yaml")
    if not confirmed:
        reasons.append("missing explicit `--i-am-chef` confirmation")
    for f in scan_dir(out_dir):
        reasons.append(f"{f.kind} in {f.file.name}:{f.line} → {f.snippet}")
    return (len(reasons) == 0, reasons)

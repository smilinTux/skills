"""Dataclasses for the plugin compiler (discovery → grouping → emit → scrub)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Root:
    """A filesystem location to scan for skills."""

    path: Path
    runtime: str          # skskills | claude-code | hermes | opencode | codex | repo
    role: str             # canonical | registry | incubator | personal | runtime | future-hook | repo
    glob: bool = False    # True if `path` contains a glob (e.g. ~/.hermes/profiles/*/skills)


@dataclass
class SkillRecord:
    """One discovered skill."""

    name: str
    path: Path
    runtime: str
    role: str
    frontmatter: dict
    skill_yaml: Optional[dict] = None
    alternates: list[Path] = field(default_factory=list)
    degraded: bool = False


@dataclass
class PluginSpec:
    """A plugin assembled as a view over skills."""

    name: str
    axis: str             # component | job-function
    version: str
    description: str
    author: dict
    skills: list[SkillRecord]
    mcp_servers: list[str]
    publish: bool = False


@dataclass
class EmitResult:
    """Outcome of rendering one plugin's envelope."""

    plugin: str
    out_dir: Path
    files: list[Path]
    warnings: list[str]

"""Discover skills across all configured homes; dedup into SkillRecord[]."""

from __future__ import annotations

import glob as _glob
import importlib.resources
import logging
from pathlib import Path
from typing import Optional

import yaml

from skskills.plugin.models import Root, SkillRecord

logger = logging.getLogger(__name__)

_ROOTS_FILENAME = "skill-roots.yaml"
# Lower number = higher precedence when two roots yield the same skill name.
_ROLE_PRECEDENCE = {
    "canonical": 0,
    "registry": 1,
    "repo": 2,
    "runtime": 3,
    "incubator": 4,
    "personal": 5,
    "future-hook": 6,
}


def parse_frontmatter(skill_md: Path) -> dict:
    """Return the YAML frontmatter block of a SKILL.md, or {} if absent/invalid."""
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        data = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _bundled_roots_path() -> Path:
    ref = importlib.resources.files("skskills.plugin").joinpath(_ROOTS_FILENAME)
    return Path(str(ref))


def load_roots(config_path: Optional[Path] = None, home: Optional[Path] = None) -> list[Root]:
    """Load root definitions, expand `~`, flag glob roots, add Hermes skills_hub."""
    home = home or Path.home()
    cfg = config_path or _bundled_roots_path()
    doc = yaml.safe_load(Path(cfg).read_text()) or {}

    def _expand(p: str) -> Path:
        if p.startswith("~/"):
            return home / p[2:]
        if p == "~":
            return home
        return Path(p)

    roots: list[Root] = []
    for entry in doc.get("roots", []):
        raw = entry["path"]
        roots.append(
            Root(
                path=_expand(raw),
                runtime=entry["runtime"],
                role=entry["role"],
                glob="*" in raw,
            )
        )

    if doc.get("import_hermes_skills_hub"):
        hermes_cfg = home / ".hermes" / "config.yaml"
        if hermes_cfg.is_file():
            try:
                hdoc = yaml.safe_load(hermes_cfg.read_text()) or {}
            except yaml.YAMLError:
                hdoc = {}
            hub = hdoc.get("skills_hub") or hdoc.get("skills") or []
            for p in hub if isinstance(hub, list) else []:
                if isinstance(p, str):
                    roots.append(
                        Root(path=_expand(p), runtime="hermes", role="runtime", glob="*" in p)
                    )
    return roots


def _expand_root_dirs(root: Root) -> list[Path]:
    """Resolve a Root to concrete directories (globs expanded)."""
    if root.glob:
        return [Path(p) for p in _glob.glob(str(root.path)) if Path(p).is_dir()]
    return [root.path] if root.path.is_dir() else []


def discover(roots: list[Root]) -> list[SkillRecord]:
    """Walk every root for `<name>/SKILL.md`, dedup by name (best role wins)."""
    best: dict[str, SkillRecord] = {}
    for root in roots:
        for base in _expand_root_dirs(root):
            for skill_md in sorted(base.glob("*/SKILL.md")):
                sdir = skill_md.parent
                name = sdir.name
                fm = parse_frontmatter(skill_md)
                yaml_path = sdir / "skill.yaml"
                sy = None
                if yaml_path.is_file():
                    try:
                        sy = yaml.safe_load(yaml_path.read_text()) or {}
                    except yaml.YAMLError:
                        sy = None
                rec = SkillRecord(
                    name=name,
                    path=sdir,
                    runtime=root.runtime,
                    role=root.role,
                    frontmatter=fm,
                    skill_yaml=sy,
                    degraded=sy is None,
                )
                existing = best.get(name)
                if existing is None:
                    best[name] = rec
                elif _ROLE_PRECEDENCE.get(rec.role, 99) < _ROLE_PRECEDENCE.get(existing.role, 99):
                    rec.alternates = existing.alternates + [existing.path]
                    best[name] = rec
                else:
                    existing.alternates.append(sdir)
    return list(best.values())

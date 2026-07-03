"""Assemble PluginSpecs as views over discovered skills (catalog `plugins:` section)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from skskills.plugin.models import PluginSpec, SkillRecord

_NEVER_PUBLISH_TAG = "never-publish"


@dataclass
class PluginDef:
    """A plugin's grouping rule from catalog.yaml `plugins:`."""

    name: str
    axis: str
    version: str
    description: str
    author: dict
    include_tags: list[str] = field(default_factory=list)
    include_names: list[str] = field(default_factory=list)
    publish: bool = False


def _catalog_path() -> Path:
    # Reuse catalog.py's locator — it handles the repo-root catalog.yaml
    # (the live location) as well as the bundled/editable-install fallbacks.
    from skskills.catalog import _locate_catalog

    return _locate_catalog()


def load_plugin_defs(catalog_path: Optional[Path] = None) -> list[PluginDef]:
    """Read the top-level `plugins:` list from catalog.yaml."""
    path = catalog_path or _catalog_path()
    doc = yaml.safe_load(Path(path).read_text()) or {}
    defs: list[PluginDef] = []
    for p in doc.get("plugins", []):
        defs.append(
            PluginDef(
                name=p["name"],
                axis=p.get("axis", "component"),
                version=p.get("version", "0.1.0"),
                description=p.get("description", ""),
                author=p.get("author", {"name": "smilinTux"}),
                include_tags=list(p.get("include_tags", [])),
                include_names=list(p.get("include_names", [])),
                publish=bool(p.get("publish", False)),
            )
        )
    return defs


def _skill_tags(rec: SkillRecord) -> list[str]:
    return list((rec.skill_yaml or {}).get("tags", []))


def _skill_mcp(rec: SkillRecord) -> list[str]:
    return list(((rec.skill_yaml or {}).get("requires", {}) or {}).get("mcp", []))


def _matches(rec: SkillRecord, d: PluginDef) -> bool:
    tags = set(_skill_tags(rec))
    return bool(tags & set(d.include_tags)) or rec.name in d.include_names


def group(records: list[SkillRecord], defs: list[PluginDef]) -> list[PluginSpec]:
    """Build one PluginSpec per def, assigning matching records (multi-membership OK)."""
    specs: list[PluginSpec] = []
    for d in defs:
        members: list[SkillRecord] = []
        for rec in records:
            if not _matches(rec, d):
                continue
            if d.publish and (rec.role == "personal" or _NEVER_PUBLISH_TAG in _skill_tags(rec)):
                continue
            members.append(rec)
        mcp = sorted({s for rec in members for s in _skill_mcp(rec)})
        specs.append(
            PluginSpec(
                name=d.name,
                axis=d.axis,
                version=d.version,
                description=d.description,
                author=d.author,
                skills=members,
                mcp_servers=mcp,
                publish=d.publish,
            )
        )
    return specs

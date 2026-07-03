"""Render PluginSpecs into the Anthropic plugin/marketplace envelope."""

from __future__ import annotations

import importlib.resources
import json
from pathlib import Path
from typing import Optional

import yaml

from skskills.plugin.models import EmitResult, PluginSpec

_REGISTRY_FILENAME = "mcp-registry.yaml"


def _registry_path() -> Path:
    ref = importlib.resources.files("skskills.plugin").joinpath(_REGISTRY_FILENAME)
    return Path(str(ref))


def load_mcp_registry(path: Optional[Path] = None) -> dict:
    """Load the server-name → connection-spec map."""
    doc = yaml.safe_load(Path(path or _registry_path()).read_text()) or {}
    return doc.get("servers", {})


def render_mcp_json(servers: list[str], registry: dict, target: str) -> dict:
    """Build a `.mcp.json` dict. target ∈ {'internal','publish'}.

    Returns {"mcpServers": {...}}. For target='publish', stdio/null-publish_as
    servers are omitted; others are keyed by their `~~` placeholder with empty url.
    """
    out: dict[str, dict] = {}
    for name in servers:
        spec = registry.get(name)
        if spec is None:
            # Unknown server: emit a placeholder entry, never guess a URL.
            out[f"~~{name}"] = {"type": "http", "url": ""}
            continue
        if target == "internal":
            entry = {"type": spec["type"]}
            if spec.get("command"):
                entry["command"] = spec["command"]
            if spec.get("url"):
                entry["url"] = spec["url"]
            out[name] = entry
        else:  # publish
            placeholder = spec.get("publish_as")
            if not placeholder:
                continue  # unpublishable (stdio / no public form)
            out[placeholder] = {"type": "http", "url": ""}
    return {"mcpServers": out}


def _unpublishable(servers: list[str], registry: dict) -> list[str]:
    warns = []
    for name in servers:
        spec = registry.get(name, {})
        if not spec.get("publish_as"):
            transport = spec.get("type", "unknown")
            warns.append(
                f"server '{name}' ({transport}) has no publishable form (publish_as=null) — omitted"
            )
    return warns


def emit_plugin(spec: PluginSpec, registry: dict, out_root: Path, target: str = "internal") -> EmitResult:
    """Write plugin.json + .mcp.json (+ CONNECTORS.md when placeholders exist)."""
    pdir = out_root / spec.name
    (pdir / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    warnings: list[str] = []

    manifest = {
        "name": spec.name,
        "version": spec.version,
        "description": spec.description,
        "author": spec.author,
    }
    mpath = pdir / ".claude-plugin" / "plugin.json"
    mpath.write_text(json.dumps(manifest, indent=2) + "\n")
    files.append(mpath)

    mcp = render_mcp_json(spec.mcp_servers, registry, target)
    mcp_path = pdir / ".mcp.json"
    mcp_path.write_text(json.dumps(mcp, indent=2) + "\n")
    files.append(mcp_path)

    placeholders = [k for k in mcp["mcpServers"] if k.startswith("~~")]
    if target == "publish":
        warnings.extend(_unpublishable(spec.mcp_servers, registry))
    if placeholders or target == "publish":
        rows = "\n".join(f"| `{p}` | connect a matching server |" for p in placeholders)
        conn = (
            "# Connectors\n\n"
            "Plugin files use `~~category` as a placeholder for whatever tool the "
            "user connects in that category.\n\n"
            "| Placeholder | How to satisfy |\n| --- | --- |\n" + rows + "\n"
        )
        cpath = pdir / "CONNECTORS.md"
        cpath.write_text(conn)
        files.append(cpath)

    return EmitResult(plugin=spec.name, out_dir=pdir, files=files, warnings=warnings)


def emit_marketplace(specs: list[PluginSpec], out_root: Path) -> Path:
    """Write the roll-up marketplace.json."""
    doc = {
        "name": "skworld-marketplace",
        "owner": {"name": "smilinTux"},
        "plugins": [
            {"name": s.name, "source": f"./{s.name}", "description": s.description}
            for s in specs
        ],
    }
    out_root.mkdir(parents=True, exist_ok=True)
    path = out_root / "marketplace.json"
    path.write_text(json.dumps(doc, indent=2) + "\n")
    return path

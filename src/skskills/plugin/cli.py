"""`skskills plugin` — compile sk* skills into the Anthropic plugin envelope."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import click

from skskills.plugin.discovery import discover, load_roots
from skskills.plugin.emit import emit_marketplace, emit_plugin, load_mcp_registry
from skskills.plugin.grouping import group, load_plugin_defs
from skskills.plugin.scrub import gate_publish

_KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _opt_path(v: Optional[str]) -> Optional[Path]:
    return Path(v) if v else None


def _load_specs(roots: Optional[str], catalog: Optional[str]):
    records = discover(load_roots(config_path=_opt_path(roots)))
    defs = load_plugin_defs(catalog_path=_opt_path(catalog))
    return group(records, defs)


@click.group()
def plugin() -> None:
    """Compile sk* skills into the Anthropic plugin/marketplace envelope."""


@plugin.command(name="discover")
@click.option("--roots", default=None, help="Path to a skill-roots.yaml override.")
def discover_cmd(roots: Optional[str]) -> None:
    """List discovered skills across all skill homes."""
    for rec in sorted(discover(load_roots(config_path=_opt_path(roots))), key=lambda r: r.name):
        alt = f"  (+{len(rec.alternates)} alt)" if rec.alternates else ""
        click.echo(f"{rec.name:<28} {rec.role:<12} {rec.runtime}{alt}")


@plugin.command()
@click.option("--plugin", "only", default=None, help="Build a single plugin by name.")
@click.option("--roots", default=None, help="skill-roots.yaml override.")
@click.option("--catalog", default=None, help="catalog.yaml override.")
@click.option("--registry", default=None, help="mcp-registry.yaml override.")
@click.option("--out", default="dist", help="Output directory (default: dist/).")
def build(only, roots, catalog, registry, out) -> None:
    """Build the internal envelope for all (or one) plugin."""
    specs = _load_specs(roots, catalog)
    if only:
        specs = [s for s in specs if s.name == only]
        if not specs:
            raise click.ClickException(f"no plugin named '{only}'")
    reg = load_mcp_registry(_opt_path(registry))
    out_root = Path(out)
    for spec in specs:
        res = emit_plugin(spec, reg, out_root, target="internal")
        click.echo(f"built {spec.name}: {len(res.files)} files, {len(spec.skills)} skills")
        for w in res.warnings:
            click.echo(f"  warn: {w}")
    emit_marketplace(specs, out_root)
    click.echo(f"marketplace.json → {out_root / 'marketplace.json'}")


@plugin.command()
@click.option("--out", default="dist", help="Directory to validate.")
def validate(out) -> None:
    """Validate every emitted plugin.json (valid JSON + kebab-case name)."""
    root = Path(out)
    manifests = sorted(root.glob("*/.claude-plugin/plugin.json"))
    if not manifests:
        raise click.ClickException(f"no plugin.json found under {root}")
    failed = False
    for m in manifests:
        try:
            doc = json.loads(m.read_text())
        except json.JSONDecodeError as e:
            click.echo(f"FAIL {m}: invalid JSON ({e})")
            failed = True
            continue
        name = doc.get("name", "")
        if not _KEBAB.match(name):
            click.echo(f"FAIL {m}: name '{name}' is not kebab-case")
            failed = True
        else:
            click.echo(f"ok   {name}")
    if failed:
        raise click.ClickException("validation failed")


@plugin.command()
@click.option("--plugin", "only", required=True, help="Plugin to publish.")
@click.option("--roots", default=None)
@click.option("--catalog", default=None)
@click.option("--registry", default=None)
@click.option("--out", default="dist-publish", help="Publish build directory.")
@click.option("--i-am-chef", "confirmed", is_flag=True, help="Explicit publish confirmation.")
def publish(only, roots, catalog, registry, out, confirmed) -> None:
    """Build for the publish target and enforce the three-gate scrub."""
    specs = [s for s in _load_specs(roots, catalog) if s.name == only]
    if not specs:
        raise click.ClickException(f"no plugin named '{only}'")
    spec = specs[0]
    reg = load_mcp_registry(_opt_path(registry))
    out_root = Path(out)
    res = emit_plugin(spec, reg, out_root, target="publish")
    for w in res.warnings:
        click.echo(f"warn: {w}")
    ok, reasons = gate_publish(spec, res.out_dir, confirmed=confirmed)
    if not ok:
        for r in reasons:
            click.echo(f"BLOCKED: {r}")
        raise click.ClickException("publish gate refused — nothing published")
    click.echo(f"clean: {spec.name} passed all publish gates (artifacts in {res.out_dir})")


@plugin.command()
@click.argument("ref")
def add(ref) -> None:
    """Inbound: show the command to install an external marketplace/plugin."""
    click.echo(f"Run: claude plugin marketplace add {ref}")
    click.echo("Then register its .mcp.json via: skcapstone register")

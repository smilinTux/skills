# skskills — Dependents & Dependency Map

_Last verified: 2026-07-03 (skskills 0.2.0)._

This documents who depends on `skskills`, exactly which APIs they consume, and
what the new `skskills.plugin` compiler means for future integration work. Keep
this current when the public API changes.

## Who depends on skskills

| Dependent | How it declares the dep | Coupling |
|---|---|---|
| **skcapstone** | `pyproject.toml`: `skskills>=0.1.1` (satisfied by 0.2.0) | Heavy — imports 7 modules across ~15 source files + 8 test files |
| Hermes runtime | via its `skills_hub` config listing skill dirs (no Python import) | Loose — filesystem convention only |
| Claude Code / Cowork | consumes emitted `.claude-plugin/` envelope (no import) | Loose — file format only |

No other `skcapstone-repos/*` package imports skskills directly.

## API surface skcapstone consumes

These are the ONLY skskills symbols skcapstone imports. Treat them as the public
contract — do not break them without a coordinated skcapstone update.

| skskills module | Symbols used by skcapstone | Used in (skcapstone) |
|---|---|---|
| `skskills.loader` | `SkillLoader` | `session_skills.py`, `discovery.py` |
| `skskills.models` | `parse_skill_yaml`, `SkillStatus` | `session_skills.py`, `runtime.py` |
| `skskills.catalog` | `SkillCatalog` | `discovery.py` |
| `skskills.registry` | `SkillRegistry` | `mcp_server.py`, `registry_client.py`, `install_wizard.py` |
| `skskills.aggregator` | `SkillAggregator` | `mcp_tools/skills_tools.py`, `providers/local.py`, `_cli_monolith.py` |
| `skskills.remote` | `RemoteRegistry` | `registry_client.py` |
| `skskills.installer` | `install_from_catalog`, `install_from_local` | `install_wizard.py` |

**The `skskills.plugin` compiler added in 0.2.0 touches none of these** — it is a
new, additive subpackage. skcapstone is unaffected by it today.

## The new `skskills.plugin` subpackage (0.2.0)

The plugin compiler (`skskills plugin` CLI: `discover`/`build`/`validate`/`publish`/`add`)
compiles sk* skills into the Anthropic plugin/marketplace envelope. See:
- Design: `~/clawd/docs/superpowers/specs/2026-07-03-skskills-plugin-compiler-design.md`
- Plan: `~/clawd/docs/superpowers/plans/2026-07-03-skskills-plugin-compiler.md`

Modules: `plugin/models.py`, `discovery.py`, `grouping.py`, `emit.py`, `scrub.py`, `cli.py`.
Config (bundled): `plugin/skill-roots.yaml`, `plugin/mcp-registry.yaml`.
Plugin group defs live in the top-level `plugins:` key of `catalog.yaml`
(`src/skskills/catalog.yaml` is a **symlink** to the repo-root `catalog.yaml` — the
single source of truth; `_locate_catalog()` resolves through it).

### Future integration work (not yet done)
1. **Wire `skskills plugin add` into `skcapstone register`** so inbound (Anthropic/
   partner) plugins register their `.mcp.json` with sk* runtimes. (Design rollout §4.)
2. **Per-plugin MCP scoping**: today skcapstone registers MCP servers globally; the
   plugin envelope scopes servers per-plugin via `requires.mcp`. Adopting that gives
   least-privilege + smaller tool context. This is the main architectural payoff.
3. **Publish path stays dark** by default (gated: `publish: true` + `--i-am-chef` +
   clean scrub). No plugin ships `publish: true`; no public marketplace is wired.

## Verification status (2026-07-03)

- skskills own suite: **131/131 pass**.
- skcapstone against skskills 0.2.0: **45/47 skskills-touching tests pass**. The 2
  failures are in `tests/test_discovery.py::TestDiscoverSkillsRemoteRegistry`
  (`test_remote_registry_fields_default`, `test_remote_registry_probed_when_skskills_available`).
  **Cause: pre-existing network dependency**, not a regression — they assume the
  remote registry `https://skskills.skworld.io/api` is unreachable, but it is live
  (returns ~19 skills), so `registry_available` comes back `True` instead of the
  asserted `False`. Fix (skcapstone-side, out of scope here): mock `RemoteRegistry`
  in those tests so they don't hit the live registry.

## Version discipline

`pyproject.toml` `version` and `src/skskills/__init__.py` `__version__` MUST match.
They had drifted (0.1.1 vs 0.1.0); realigned to **0.2.0** on 2026-07-03.

# tests/plugin/test_grouping.py
from pathlib import Path

from skskills.plugin.grouping import PluginDef, group, load_plugin_defs
from skskills.plugin.models import SkillRecord


def _rec(name, tags, role="canonical", mcp=None):
    sy = {"tags": tags}
    if mcp is not None:
        sy["requires"] = {"mcp": mcp}
    return SkillRecord(
        name=name, path=Path(f"/s/{name}"), runtime="skskills", role=role,
        frontmatter={"name": name, "description": "d"}, skill_yaml=sy,
    )


def test_group_by_tags_and_names_multi_membership():
    recs = [
        _rec("chat", ["skchat", "messaging"], mcp=["skchat"]),
        _rec("who", ["identity"]),
        _rec("research", ["research"]),
    ]
    defs = [
        PluginDef(name="skcomms", axis="component", version="0.1.0",
                  description="comms", author={"name": "X"},
                  include_tags=["skchat", "messaging"], include_names=[], publish=False),
        PluginDef(name="deep-research", axis="job-function", version="0.1.0",
                  description="research", author={"name": "X"},
                  include_tags=["research"], include_names=["chat"], publish=False),
    ]
    specs = {s.name: s for s in group(recs, defs)}
    assert {r.name for r in specs["skcomms"].skills} == {"chat"}
    # chat joins deep-research too (via include_names) → multi-membership, no copy
    assert {r.name for r in specs["deep-research"].skills} == {"chat", "research"}
    assert specs["skcomms"].mcp_servers == ["skchat"]


def test_group_publish_excludes_personal_and_neverpublish():
    recs = [
        _rec("secret", ["skchat"], role="personal"),
        _rec("nope", ["skchat", "never-publish"]),
        _rec("ok", ["skchat"]),
    ]
    d = PluginDef(name="skcomms", axis="component", version="0.1.0",
                  description="c", author={"name": "X"},
                  include_tags=["skchat"], include_names=[], publish=True)
    spec = group(recs, [d])[0]
    assert {r.name for r in spec.skills} == {"ok"}


def test_load_plugin_defs_reads_catalog(tmp_path):
    cat = tmp_path / "catalog.yaml"
    cat.write_text(
        "version: '1'\n"
        "skills: []\n"
        "plugins:\n"
        "  - name: skcomms\n"
        "    axis: component\n"
        "    version: '0.1.0'\n"
        "    description: Sovereign comms\n"
        "    author: { name: 'Chef & Lumina' }\n"
        "    include_tags: [skchat, messaging]\n"
        "    publish: false\n"
    )
    defs = load_plugin_defs(catalog_path=cat)
    assert defs[0].name == "skcomms"
    assert defs[0].include_tags == ["skchat", "messaging"]
    assert defs[0].include_names == []
    assert defs[0].publish is False

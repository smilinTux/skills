from pathlib import Path

from skskills.plugin.models import EmitResult, PluginSpec, Root, SkillRecord


def test_skillrecord_defaults():
    rec = SkillRecord(
        name="chat",
        path=Path("/x/chat"),
        runtime="skskills",
        role="canonical",
        frontmatter={"name": "chat", "description": "d"},
    )
    assert rec.skill_yaml is None
    assert rec.alternates == []
    assert rec.degraded is False


def test_pluginspec_and_emitresult():
    spec = PluginSpec(
        name="skcomms",
        axis="component",
        version="0.1.0",
        description="Sovereign comms",
        author={"name": "Chef & Lumina"},
        skills=[],
        mcp_servers=["skchat"],
    )
    assert spec.publish is False
    res = EmitResult(plugin="skcomms", out_dir=Path("/d"), files=[], warnings=[])
    assert res.plugin == "skcomms"
    assert Root(path=Path("/r"), runtime="hermes", role="runtime").glob is False

import json
from pathlib import Path

from skskills.plugin.emit import (
    emit_marketplace, emit_plugin, load_mcp_registry, render_mcp_json,
)
from skskills.plugin.models import PluginSpec, SkillRecord


def _spec(mcp, publish=False):
    return PluginSpec(
        name="skcomms", axis="component", version="0.2.0",
        description="Sovereign comms", author={"name": "Chef & Lumina"},
        skills=[SkillRecord(name="chat", path=Path("/s/chat"), runtime="skskills",
                            role="canonical", frontmatter={"name": "chat", "description": "d"})],
        mcp_servers=mcp, publish=publish,
    )


REGISTRY = {
    "skchat": {"type": "stdio", "command": "~/.skenv/bin/skchat-mcp", "publish_as": None},
    "skcomms": {"type": "http", "url": "http://127.0.0.1:9384/api/v1/inbox",
                "publish_as": "~~sovereign comms"},
}


def test_render_internal_stdio_and_http():
    out = render_mcp_json(["skchat", "skcomms"], REGISTRY, "internal")
    assert out["mcpServers"]["skchat"] == {"type": "stdio", "command": "~/.skenv/bin/skchat-mcp"}
    assert out["mcpServers"]["skcomms"]["url"] == "http://127.0.0.1:9384/api/v1/inbox"


def test_render_publish_omits_null_publish_as():
    out = render_mcp_json(["skchat", "skcomms"], REGISTRY, "publish")
    assert "skchat" not in out["mcpServers"]                 # stdio, not publishable
    assert "~~sovereign comms" in out["mcpServers"]          # placeholder-keyed
    assert out["mcpServers"]["~~sovereign comms"]["url"] == ""


def test_emit_plugin_writes_manifest_and_mcp(tmp_path):
    res = emit_plugin(_spec(["skchat", "skcomms"]), REGISTRY, tmp_path, target="internal")
    manifest = json.loads((tmp_path / "skcomms" / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["name"] == "skcomms"
    assert manifest["version"] == "0.2.0"
    assert manifest["author"] == {"name": "Chef & Lumina"}
    mcp = json.loads((tmp_path / "skcomms" / ".mcp.json").read_text())
    assert "skchat" in mcp["mcpServers"]
    assert (tmp_path / "skcomms" / ".mcp.json") in res.files


def test_emit_plugin_publish_warns_on_unpublishable(tmp_path):
    res = emit_plugin(_spec(["skchat"], publish=True), REGISTRY, tmp_path, target="publish")
    assert any("skchat" in w and "stdio" in w.lower() for w in res.warnings)
    conn_path = tmp_path / "skcomms" / "CONNECTORS.md"
    assert conn_path.is_file()                        # CONNECTORS.md written for publish target
    assert conn_path.read_text().startswith("# Connectors")


def test_emit_plugin_internal_no_connectors_for_concrete_servers(tmp_path):
    # skcomms resolves to a real URL on internal target → no placeholder → no CONNECTORS.md
    res = emit_plugin(_spec(["skcomms"]), REGISTRY, tmp_path, target="internal")
    assert not (tmp_path / "skcomms" / "CONNECTORS.md").is_file()
    assert all("CONNECTORS.md" not in f.name for f in res.files)


def test_emit_marketplace(tmp_path):
    p = emit_marketplace([_spec(["skchat"])], tmp_path)
    doc = json.loads(p.read_text())
    assert doc["plugins"][0]["name"] == "skcomms"
    assert doc["plugins"][0]["source"] == "./skcomms"

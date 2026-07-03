import json
from pathlib import Path

from skskills.plugin.models import PluginSpec
from skskills.plugin.scrub import gate_publish, scan_dir


def _spec(publish):
    return PluginSpec(name="skcomms", axis="component", version="0.1.0",
                      description="c", author={"name": "X"}, skills=[],
                      mcp_servers=[], publish=publish)


def test_scan_catches_secret_and_private_ip(tmp_path):
    (tmp_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"x": {"url": "http://127.0.0.1:9384"}}})
    )
    (tmp_path / "note.md").write_text("token ghp_" + "A" * 36 + "\n")
    kinds = {f.kind for f in scan_dir(tmp_path)}
    assert "private-endpoint" in kinds
    assert "secret" in kinds


def test_scan_clean_dir(tmp_path):
    (tmp_path / "plugin.json").write_text(json.dumps({"name": "skcomms"}))
    assert scan_dir(tmp_path) == []


def test_gate_blocks_without_publish_flag(tmp_path):
    ok, reasons = gate_publish(_spec(publish=False), tmp_path, confirmed=True)
    assert ok is False
    assert any("publish: true" in r for r in reasons)


def test_gate_blocks_without_confirmation(tmp_path):
    ok, reasons = gate_publish(_spec(publish=True), tmp_path, confirmed=False)
    assert ok is False
    assert any("--i-am-chef" in r for r in reasons)


def test_gate_blocks_on_findings(tmp_path):
    (tmp_path / "bad.mcp.json").write_text('{"url": "http://192.168.0.158:9384"}')
    ok, reasons = gate_publish(_spec(publish=True), tmp_path, confirmed=True)
    assert ok is False
    assert any("private-endpoint" in r for r in reasons)


def test_gate_passes_when_all_clear(tmp_path):
    (tmp_path / "plugin.json").write_text('{"name": "skcomms"}')
    ok, reasons = gate_publish(_spec(publish=True), tmp_path, confirmed=True)
    assert ok is True
    assert reasons == []


def test_scan_catches_tailnet_tsnet_and_172(tmp_path):
    (tmp_path / "a.json").write_text('{"u": "http://100.101.5.6:9386"}')       # 100.64/10 in-range
    (tmp_path / "b.json").write_text('{"u": "http://foo.tail204f0c.ts.net:9386/sse"}')  # MagicDNS
    (tmp_path / "c.json").write_text('{"u": "http://172.17.0.2:5432"}')        # 172.16/12 (docker)
    hits = {(f.kind, f.file.name) for f in scan_dir(tmp_path)}
    assert ("private-endpoint", "a.json") in hits
    assert ("private-endpoint", "b.json") in hits
    assert ("private-endpoint", "c.json") in hits


def test_scan_ignores_out_of_range_100_block(tmp_path):
    # 100.63.x and 100.128.x are OUTSIDE the tailnet CGNAT 100.64-127 range; 100.5.x is public
    (tmp_path / "ok.json").write_text('{"a": "100.63.1.1", "b": "100.128.1.1", "c": "100.5.5.5"}')
    assert scan_dir(tmp_path) == []

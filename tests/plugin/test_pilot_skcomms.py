"""End-to-end pilot: the bundled configs compile a valid skcomms plugin."""
import json

from click.testing import CliRunner

from skskills.cli import main
from skskills.plugin.emit import load_mcp_registry
from skskills.plugin.grouping import load_plugin_defs


def test_skcomms_is_defined_in_bundled_catalog():
    names = {d.name for d in load_plugin_defs()}
    assert "skcomms" in names


def test_bundled_registry_has_skchat_stdio():
    reg = load_mcp_registry()
    assert reg["skchat"]["type"] == "stdio"
    assert reg["skchat"]["publish_as"] is None


def test_skcomms_builds_and_validates(tmp_path):
    out = tmp_path / "dist"
    b = CliRunner().invoke(main, ["plugin", "build", "--plugin", "skcomms", "--out", str(out)])
    assert b.exit_code == 0, b.output
    manifest = out / "skcomms" / ".claude-plugin" / "plugin.json"
    assert manifest.is_file()
    assert json.loads(manifest.read_text())["name"] == "skcomms"
    v = CliRunner().invoke(main, ["plugin", "validate", "--out", str(out)])
    assert v.exit_code == 0, v.output

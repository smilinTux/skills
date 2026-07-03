from pathlib import Path

from click.testing import CliRunner

from skskills.cli import main


def _seed_skill(root: Path, name, tags, mcp=None):
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: d\n---\n# {name}\n")
    sy = f"name: {name}\ntags: {tags}\n"
    if mcp:
        sy += f"requires:\n  mcp: {mcp}\n"
    (d / "skill.yaml").write_text(sy)


def _seed_roots(tmp_path, skills_dir):
    roots = tmp_path / "roots.yaml"
    roots.write_text(
        f"roots:\n  - path: '{skills_dir}'\n    runtime: skskills\n    role: canonical\n"
    )
    return roots


def _seed_catalog(tmp_path):
    cat = tmp_path / "catalog.yaml"
    cat.write_text(
        "version: '1'\nskills: []\nplugins:\n"
        "  - name: skcomms\n    axis: component\n    version: '0.1.0'\n"
        "    description: comms\n    author: { name: 'X' }\n"
        "    include_tags: [skchat]\n    publish: false\n"
    )
    return cat


def test_plugin_build_creates_envelope(tmp_path):
    skills = tmp_path / "skills"
    _seed_skill(skills, "chat", "[skchat]", mcp="[skchat]")
    roots = _seed_roots(tmp_path, skills)
    cat = _seed_catalog(tmp_path)
    out = tmp_path / "dist"
    r = CliRunner().invoke(
        main,
        ["plugin", "build", "--roots", str(roots), "--catalog", str(cat), "--out", str(out)],
    )
    assert r.exit_code == 0, r.output
    assert (out / "skcomms" / ".claude-plugin" / "plugin.json").is_file()
    assert (out / "marketplace.json").is_file()


def test_plugin_validate_passes(tmp_path):
    skills = tmp_path / "skills"
    _seed_skill(skills, "chat", "[skchat]", mcp="[skchat]")
    roots = _seed_roots(tmp_path, skills)
    cat = _seed_catalog(tmp_path)
    out = tmp_path / "dist"
    CliRunner().invoke(main, ["plugin", "build", "--roots", str(roots),
                              "--catalog", str(cat), "--out", str(out)])
    r = CliRunner().invoke(main, ["plugin", "validate", "--out", str(out)])
    assert r.exit_code == 0, r.output
    assert "skcomms" in r.output


def test_plugin_publish_blocked_without_flag(tmp_path):
    skills = tmp_path / "skills"
    _seed_skill(skills, "chat", "[skchat]", mcp="[skchat]")
    roots = _seed_roots(tmp_path, skills)
    cat = _seed_catalog(tmp_path)   # publish: false
    out = tmp_path / "dist"
    r = CliRunner().invoke(
        main,
        ["plugin", "publish", "--plugin", "skcomms", "--roots", str(roots),
         "--catalog", str(cat), "--out", str(out), "--i-am-chef"],
    )
    assert r.exit_code != 0
    assert "publish: true" in r.output

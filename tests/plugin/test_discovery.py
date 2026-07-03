# tests/plugin/test_discovery.py
from pathlib import Path

from skskills.plugin.discovery import discover, load_roots, parse_frontmatter
from skskills.plugin.models import Root


def _make_skill(root: Path, name: str, desc: str, extra_yaml: str = "") -> None:
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\n\n# {name}\n"
    )
    if extra_yaml:
        (d / "skill.yaml").write_text(extra_yaml)


def test_parse_frontmatter(tmp_path):
    md = tmp_path / "SKILL.md"
    md.write_text("---\nname: chat\ndescription: talk\n---\nbody")
    fm = parse_frontmatter(md)
    assert fm["name"] == "chat"
    assert fm["description"] == "talk"


def test_parse_frontmatter_missing(tmp_path):
    md = tmp_path / "SKILL.md"
    md.write_text("# no frontmatter\n")
    assert parse_frontmatter(md) == {}


def test_discover_dedups_canonical_wins(tmp_path):
    canon = tmp_path / "skskills"
    incub = tmp_path / "clawd-skills"
    _make_skill(canon, "chat", "canonical chat")
    _make_skill(incub, "chat", "incubator chat")
    roots = [
        Root(path=incub, runtime="claude-code", role="incubator"),
        Root(path=canon, runtime="skskills", role="canonical"),
    ]
    recs = discover(roots)
    chat = [r for r in recs if r.name == "chat"]
    assert len(chat) == 1
    assert chat[0].role == "canonical"
    assert incub / "chat" in chat[0].alternates


def test_discover_attaches_skill_yaml(tmp_path):
    root = tmp_path / "skskills"
    _make_skill(root, "who", "who am i", extra_yaml="name: who\ntags: [identity]\n")
    recs = discover([Root(path=root, runtime="skskills", role="canonical")])
    who = next(r for r in recs if r.name == "who")
    assert who.skill_yaml["tags"] == ["identity"]
    assert who.degraded is False


def test_discover_missing_skill_yaml_marks_degraded(tmp_path):
    root = tmp_path / "skskills"
    _make_skill(root, "solo", "no yaml")
    rec = discover([Root(path=root, runtime="skskills", role="canonical")])[0]
    assert rec.degraded is True


def test_load_roots_expands_home(tmp_path):
    cfg = tmp_path / "roots.yaml"
    cfg.write_text(
        "roots:\n"
        "  - path: '~/clawd/skskills/skills'\n"
        "    runtime: skskills\n"
        "    role: canonical\n"
        "  - path: '~/.hermes/profiles/*/skills'\n"
        "    runtime: hermes\n"
        "    role: runtime\n"
    )
    roots = load_roots(config_path=cfg, home=Path("/home/test"))
    assert roots[0].path == Path("/home/test/clawd/skskills/skills")
    assert roots[0].glob is False
    assert roots[1].glob is True

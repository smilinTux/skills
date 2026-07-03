import shutil
import subprocess

from click.testing import CliRunner

from skskills.cli import main


class _Recorder:
    """Records subprocess.run calls; returns a success-like CompletedProcess."""

    def __init__(self):
        self.calls: list[list[str]] = []

    def __call__(self, argv, *args, **kwargs):
        self.calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0)


def test_add_runs_marketplace_add_and_register_when_both_on_path(monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "run", recorder)

    r = CliRunner().invoke(main, ["plugin", "add", "somemarketplace"])

    assert r.exit_code == 0, r.output
    assert any(
        "claude" in call[0] and "marketplace" in call and "add" in call
        and "somemarketplace" in call
        for call in recorder.calls
    ), recorder.calls
    assert ["skcapstone", "register"] in recorder.calls


def test_add_degrades_gracefully_when_neither_on_path(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)

    calls = []

    def _unexpected_run(argv, *args, **kwargs):
        calls.append(argv)
        raise AssertionError("subprocess.run should not be called")

    monkeypatch.setattr(subprocess, "run", _unexpected_run)

    r = CliRunner().invoke(main, ["plugin", "add", "somemarketplace"])

    assert r.exit_code == 0, r.output
    assert "claude plugin marketplace add somemarketplace" in r.output
    assert "skcapstone register" in r.output
    assert calls == []


def test_add_is_non_fatal_when_subprocess_run_raises(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")

    def _raise(argv, *args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(subprocess, "run", _raise)

    r = CliRunner().invoke(main, ["plugin", "add", "somemarketplace"])

    assert r.exit_code == 0, r.output
    assert "warn" in r.output.lower()

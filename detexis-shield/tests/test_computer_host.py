import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("computer_host", Path("tools/computer.py"))
computer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(computer)


def test_new_computer_credentials_are_random_and_never_overwritten(tmp_path):
    first, second = tmp_path / "first.env", tmp_path / "second.env"
    computer.prepare_env(first, False)
    computer.prepare_env(second, False)
    original = first.read_text()
    assert original != second.read_text()
    assert len(original.splitlines()[0].split("=", 1)[1]) == 64
    computer.prepare_env(first, True)
    assert first.read_text() == original


def test_missing_credentials_for_existing_volume_require_recovery(tmp_path):
    target = tmp_path / "missing.env"
    with pytest.raises(RuntimeError, match="Restore that private file"):
        computer.prepare_env(target, True)
    assert not target.exists()


def test_empty_saved_configuration_cannot_fall_back_to_development_password(tmp_path):
    target = tmp_path / "empty.env"
    target.write_text("")
    with pytest.raises(RuntimeError, match="Invalid .computer.env"):
        computer.prepare_env(target, False)


def test_other_shell_database_password_does_not_override_saved_instance(monkeypatch):
    from types import SimpleNamespace
    observed = {}
    monkeypatch.setenv("POSTGRES_PASSWORD", "other-project")
    def run(*args, **kwargs):
        observed.update(kwargs["env"])
        return SimpleNamespace(returncode=0, stdout="ok")
    monkeypatch.setattr(computer.subprocess, "run", run)
    computer.command("info", capture=True)
    assert "POSTGRES_PASSWORD" not in observed

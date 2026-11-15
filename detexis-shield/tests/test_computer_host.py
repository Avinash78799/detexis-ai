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


def test_stop_includes_both_optional_services_without_removing_data(monkeypatch, tmp_path):
    calls = []
    saved = tmp_path / "saved.env"
    saved.write_text("POSTGRES_PASSWORD=" + "a"*64)
    monkeypatch.setattr(computer, "ENV", saved)
    monkeypatch.setattr(computer, "command", lambda *args, **kwargs: "")
    monkeypatch.setattr(computer, "compose", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr("sys.argv", ["computer.py", "stop"])
    computer.main()
    assert calls == [("--profile","malware","--profile","localtls","stop")]


def test_local_https_start_is_explicit_and_never_installs_host_trust(monkeypatch, tmp_path, capsys):
    import io
    calls = []
    saved = tmp_path / "saved.env"
    computer.prepare_env(saved, False)
    original = saved.read_text()
    monkeypatch.setattr(computer, "ENV", saved)
    monkeypatch.setattr(computer, "command", lambda *args, **kwargs: "")
    def compose(*args, **kwargs):
        calls.append(args)
        return "127.0.0.1:8000" if args[0] == "port" else None
    monkeypatch.setattr(computer, "compose", compose)
    monkeypatch.setattr(computer, "urlopen", lambda *args, **kwargs: io.BytesIO(b'{"ok":true}'))
    monkeypatch.setattr("sys.argv", ["computer.py", "start", "--local-https"])
    computer.main()
    assert calls[0] == ("--profile","localtls","up","--build","-d","--wait")
    assert saved.read_text() == original
    output = capsys.readouterr().out
    assert "https://localhost:8443/app" in output and original.splitlines()[0].split("=",1)[1] not in output


def test_compose_lifecycle_loads_the_local_proxy_definition(monkeypatch):
    calls = []
    monkeypatch.setattr(computer, "command", lambda *args, **kwargs: calls.append(args))
    computer.compose("ps")
    assert "docker-compose.local-tls.yml" in calls[0]


def test_local_https_flag_rejected_before_operations_for_other_actions(monkeypatch):
    monkeypatch.setattr(computer, "command", lambda *args, **kwargs: pytest.fail("No operation should run"))
    monkeypatch.setattr("sys.argv", ["computer.py", "backup", "--local-https"])
    with pytest.raises(SystemExit):
        computer.main()

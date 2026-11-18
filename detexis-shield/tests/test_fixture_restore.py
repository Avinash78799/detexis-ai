import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("fixture_restore", Path("tools/rehearse_fixture_restore.py"))
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def container(service="db", running=False, project="shield-perf-test"):
    return {"Id": service, "Config": {"Labels": {"com.docker.compose.project": project,
            "com.docker.compose.service": service}}, "State": {"Running": running}}


def test_restore_requires_a_stopped_disposable_stack():
    assert tool.validate_fixture("shield-perf-test", [container(), container("worker")]) == "db"
    for items in [[], [container(), container()], [container(running=True)],
                  [container(), container("worker", running=True)],
                  [container(project="detexis-shield-computer")]]:
        with pytest.raises(ValueError):
            tool.validate_fixture("shield-perf-test", items)


def test_restore_refuses_computer_hosting_and_arbitrary_projects():
    for project in ["detexis-shield-computer", "shield-perf-", "shield-perf-test;bad", "production"]:
        with pytest.raises(ValueError):
            tool.validate_fixture(project, [container(project=project)])

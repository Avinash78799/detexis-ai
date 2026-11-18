import importlib.util
from pathlib import Path
import sys

import pytest


def load(monkeypatch):
    folder=Path(__file__).resolve().parents[1]/"tools"
    monkeypatch.syspath_prepend(str(folder))
    spec=importlib.util.spec_from_file_location("multitenant_benchmark",folder/"benchmark_multitenant.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_latency_report_keeps_tail_and_empty_samples_explicit(monkeypatch):
    tool=load(monkeypatch)
    result=tool.summary(list(range(1,101)))
    assert result=={"samples":100,"median_ms":50.5,"p95_ms":95,"max_ms":100}
    assert tool.summary([])=={"samples":0,"median_ms":None,"p95_ms":None,"max_ms":None}


def test_configured_ports_are_not_proof_of_actual_loopback_publication(monkeypatch):
    tool=load(monkeypatch)
    expected={'8443/tcp':[{'HostIp':'127.0.0.1','HostPort':'18443'},{'HostIp':'::1','HostPort':'18443'}]}
    tool.validate_proxy_ports({'HostConfig':{'PortBindings':expected},'NetworkSettings':{'Ports':expected}})
    for actual in [{'8443/tcp':[]},{'8443/tcp':None},{'8443/tcp':[{'HostIp':'0.0.0.0','HostPort':'18443'},{'HostIp':'::1','HostPort':'18443'}]}]:
        with pytest.raises(RuntimeError):
            tool.validate_proxy_ports({'HostConfig':{'PortBindings':expected},'NetworkSettings':{'Ports':actual}})


@pytest.mark.parametrize("project,rate",[("detexis-shield-computer",500),("shield-perf-test",501)])
def test_unsafe_target_or_rate_refused_before_docker_and_fixture_creation(monkeypatch,tmp_path,project,rate):
    tool=load(monkeypatch)
    def forbidden(*args):
        raise AssertionError("Docker must not be invoked for invalid arguments")
    monkeypatch.setattr(tool,"docker",forbidden)
    output=tmp_path/"report.json"
    monkeypatch.setattr(sys,"argv",["benchmark_multitenant.py","--project",project,"--rate",str(rate),
                                   "--ca",str(tmp_path/"absent.crt"),"--output",str(output),"--confirm-disposable"])
    with pytest.raises(SystemExit) as error:tool.main()
    assert error.value.code==2
    assert not output.exists()

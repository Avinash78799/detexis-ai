"""A fast client must not hide another client's failed overhead target."""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

spec = importlib.util.spec_from_file_location('sensor_socket_benchmark', Path(__file__).parents[1] / 'tools/benchmark_sensor_sockets.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def test_per_client_tail_failure_is_not_hidden_by_pooled_percentiles(monkeypatch):
    @contextmanager
    def collector(online):
        yield 'synthetic', {'events':960, 'redaction_failures':0}

    @contextmanager
    def host(*args):
        yield 'synthetic', SimpleNamespace(client=SimpleNamespace(dropped=0, q=SimpleNamespace(qsize=lambda:0)))

    clients = [([1]*100, [1]*100, [0]*100) for _ in range(3)]
    clients.append(([1]*100, [1]*94+[12]*6, [0]*94+[11]*6))
    monkeypatch.setattr(benchmark, 'collector', collector)
    monkeypatch.setattr(benchmark, 'host', host)
    monkeypatch.setattr(benchmark, 'paired_clients', lambda *args:clients)
    result = benchmark.measure('asgi', True, 100, concurrency=4)
    assert result['sender']['expected_synthetic_events'] == 960
    for profile in result['profiles'].values():
        assert profile['paired_added_latency']['p95_ms'] == 0
        assert profile['per_client_added_latency'][-1]['p95_ms'] == 11
        assert profile['target_passed'] is False


def test_request_preparation_is_outside_all_measured_pairs(monkeypatch):
    events = []
    class Client:
        def __init__(self, **kwargs):pass
        def __enter__(self):return self
        def __exit__(self, *args):pass
        def build_request(self, method, path):
            assert method == 'GET'
            events.append('build')
            return object()
        def send(self, prepared):
            events.append('send')
            return SimpleNamespace(status_code=200, content=b'ok')
    def clock():
        events.append('clock')
        return len(events)*1000000
    monkeypatch.setattr(benchmark.httpx, 'Client', Client)
    monkeypatch.setattr(benchmark.time, 'perf_counter_ns', clock)
    clients = benchmark.paired_clients('synthetic','q=fixture',100,1)
    assert events[:2] == ['build','build']
    assert events.count('build') == 2
    assert events.count('send') == 240
    assert all(len(values) == 100 for values in clients[0])
    assert events[2:5] == ['clock','send','clock']


def test_waitress_thread_setting_reaches_host_and_report(monkeypatch):
    observed = []
    @contextmanager
    def collector(online):
        yield 'synthetic', {'events':240, 'redaction_failures':0}
    @contextmanager
    def host(framework, wrap, server, threads):
        observed.append((framework, server, threads))
        yield 'synthetic', SimpleNamespace(client=SimpleNamespace(dropped=0, q=SimpleNamespace(qsize=lambda:0)))
    monkeypatch.setattr(benchmark, 'collector', collector)
    monkeypatch.setattr(benchmark, 'host', host)
    monkeypatch.setattr(benchmark, 'paired_clients', lambda *args:[([1]*100,[1]*100,[0]*100)])
    result = benchmark.measure('wsgi', True, 100, 'waitress', wsgi_threads=8)
    assert observed == [('wsgi', 'waitress', 8)]
    assert result['wsgi_threads'] == 8


@pytest.mark.parametrize('threads', ['0', '65'])
def test_invalid_thread_count_stops_before_starting_listeners(monkeypatch, threads):
    monkeypatch.setattr('sys.argv', ['benchmark', '--wsgi-threads', threads])
    monkeypatch.setattr(benchmark, 'measure', lambda *args:pytest.fail('must not start a measurement'))
    with pytest.raises(SystemExit) as error:
        benchmark.main()
    assert error.value.code == 2

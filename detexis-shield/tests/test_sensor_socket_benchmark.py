"""A fast client must not hide another client's failed overhead target."""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
from types import SimpleNamespace

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

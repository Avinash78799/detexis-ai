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


def test_loaded_sdk_mismatch_stops_before_measurement(monkeypatch, tmp_path):
    monkeypatch.setattr('sys.argv', ['benchmark', '--output', str(tmp_path/'report.json')])
    def mismatch(root):
        raise ValueError('Loaded SDK differs from checkout')
    monkeypatch.setattr(benchmark, 'loaded_sdk_info', mismatch)
    monkeypatch.setattr(benchmark, 'measure', lambda *args:pytest.fail('must not benchmark mismatched code'))
    with pytest.raises(ValueError, match='Loaded SDK differs'):
        benchmark.main()
    assert not (tmp_path/'report.json').exists()


def test_loaded_sdk_comparison_detects_changed_bytes_with_same_filenames(tmp_path):
    destination = tmp_path/'sensor-sdk/detexis_shield'
    destination.mkdir(parents=True)
    actual = Path(benchmark.detexis_shield.__file__).resolve().parent
    for source in actual.glob('*.py'):
        (destination/source.name).write_bytes(source.read_bytes())
    assert benchmark.loaded_sdk_info(tmp_path)['matches_checkout'] is True
    (destination/'redact.py').write_bytes(b'# Different implementation\n')
    with pytest.raises(ValueError, match='Loaded SDK differs'):
        benchmark.loaded_sdk_info(tmp_path)


def test_optional_nested_profile_keeps_original_profiles_and_counts_all_events(monkeypatch):
    @contextmanager
    def collector(online):
        yield 'synthetic', {'events':360, 'redaction_failures':0}
    @contextmanager
    def host(*args):
        yield 'synthetic', SimpleNamespace(client=SimpleNamespace(dropped=0, q=SimpleNamespace(qsize=lambda:0)))
    queries = []
    def pairs(origin, query, samples, concurrency):
        queries.append(query)
        return [([1]*100, [1]*100, [0]*100)]
    monkeypatch.setattr(benchmark, 'collector', collector)
    monkeypatch.setattr(benchmark, 'host', host)
    monkeypatch.setattr(benchmark, 'paired_clients', pairs)
    result = benchmark.measure('asgi', True, 100, include_nested=True)
    assert list(result['profiles']) == ['normal','large','nested_secrets']
    assert queries[:2] == list(benchmark.request_profiles().values())
    assert 'credentials%5Bpassword%5D' in queries[-1] and 'auth.token' in queries[-1]
    assert result['sender']['expected_synthetic_events'] == 360

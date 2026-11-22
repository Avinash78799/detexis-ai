"""Measure paired-path noise with identical applications and NO sensor.

This is a diagnostic. Exit zero means the calibration completed, not that the
sensor overhead target passed. Never subtract its percentiles from SDK results.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from benchmark_sensor_sockets import host, paired_clients, summary


def calibrate(framework, samples, concurrency, threads):
    def no_sensor(app):
        app.client = SimpleNamespace(close=lambda:None)
        return app

    profiles = {}
    with host(framework, no_sensor, 'waitress', threads) as (origin, _):
        for name, query in {'normal':'q=notebook&password=synthetic-secret',
                            'large':'q='+'%3C%3E%27%22'*512+'&password=synthetic-secret'}.items():
            clients = paired_clients(origin, query, samples, concurrency)
            profiles[name] = {
                'samples':samples*concurrency,
                'pooled_path_delta_ms':summary([v for c in clients for v in c[2]]),
                'per_client_path_delta_ms':[summary(c[2]) for c in clients],
                'absolute_path_difference_ms':summary([abs(v) for c in clients for v in c[2]]),
            }
    return {'framework':framework, 'concurrent_clients':concurrency,
            'waitress_threads':threads if framework == 'wsgi' else None, 'profiles':profiles}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=200)
    parser.add_argument('--concurrency', type=int, default=4)
    parser.add_argument('--wsgi-threads', type=int, default=4)
    parser.add_argument('--framework', choices=['asgi','wsgi','both'], default='both')
    args = parser.parse_args()
    if not 100 <= args.samples <= 1000 or not 1 <= args.concurrency <= 16 or not 1 <= args.wsgi_threads <= 64:
        parser.error('Expected samples 100–1000, concurrency 1–16 and WSGI threads 1–64')
    if args.output.exists():
        parser.error('Refusing to overwrite an existing report')
    frameworks = ['asgi','wsgi'] if args.framework == 'both' else [args.framework]
    report = {'kind':'no_sensor_calibration', 'sensor_acceptance':None,
              'checked_at':datetime.now(timezone.utc).isoformat(),
              'scope':'Identical no-sensor apps on both loopback paths. No sender, collector, accounts or real traffic. Shared host scheduling and request parsing remain. This does not prove sensor latency acceptance.',
              'cases':[calibrate(f,args.samples,args.concurrency,args.wsgi_threads) for f in frameworks]}
    report['source_sha256'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in [Path(__file__),Path(__file__).with_name('benchmark_sensor_sockets.py')]}
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2)
    print(json.dumps({'report':str(args.output),'kind':report['kind'],'sensor_acceptance':None}))


if __name__ == '__main__':
    main()

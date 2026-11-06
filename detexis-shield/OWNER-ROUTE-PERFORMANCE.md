# Owner-route latency checkpoint

On 6 November 2026, the local Docker API ran `tools/benchmark_owner_routes.py`
against real PostgreSQL/Redis. The application source was commit `62afd38`.
The fixture is one synthetic account/site, 10,000 processed events and 100
incidents. It remains in the development database for inspection and is not
customer adoption. The script prints no passwords, recovery codes or sessions.

Each route received five warmups followed by 100 sequential requests through
httpx ASGITransport. This includes authentication, database work and HTML/JSON
rendering. It excludes the HTTP server, TLS, network, browser layout, JavaScript,
asset downloads, concurrent users and concurrent ingest load. `/app` serves the
workspace shell; its measurement does not include subsequent API calls.

| Route | Median ms | p95 ms |
| --- | ---: | ---: |
| Workspace shell | 0.961 | 1.232 |
| Session | 5.025 | 8.951 |
| Site list | 14.587 | 17.145 |
| Incident inbox | 7.103 | 24.922 |
| Connection diagnostics | 7.668 | 11.289 |
| Site dashboard | 13.425 | 44.087 |
| Feed refresh | 12.481 | 15.380 |

Raw results are in `owner-route-benchmark.json`. These results establish a local
checkpoint, not an availability or latency SLA. Cold-cache, larger tenant,
multi-user and deployed browser measurements remain required.

To repeat on a development stack only (creates a new retained synthetic fixture):

```sh
docker compose cp tools/benchmark_owner_routes.py api:/tmp/benchmark_owner_routes.py
docker compose exec -T -e PYTHONPATH=/srv api python /tmp/benchmark_owner_routes.py
```

Use the same project/Compose overrides as the running stack. Do not run this
fixture generator against a production database. No actual domain is contacted
and no scan or notification is requested.

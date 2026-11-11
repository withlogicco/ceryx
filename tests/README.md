# Ceryx tests

This directory is the Ceryx test suite. It runs against a live Ceryx: either one the tests start inside the dev container, or the `ceryx` service of the Compose test stack (`compose.test.yml`).

The test image is the `test` target of the `Dockerfile`.

## Running

- Dev container: the VS Code Testing view (SQLite), or `pytest` and `CERYX_STORAGE_BACKEND=redis pytest` in a terminal. The tests start NGINX with the checkout they live in, so they also work from a local clone.
- Docker: `docker compose -f compose.test.yml run --rm test` builds and starts the test stack and runs the suite on SQLite in its `test` service. `compose.test.yml` extends the `ceryx` service of `compose.yml`, with its own project (`ceryx-test`), volumes, network and host ports (18080, 18443, 18081), so it never touches a local stack. Its `redis` and `redis-password` profiles run the same stack on Redis, without and with a password: `docker compose -f compose.test.yml --profile redis run --rm test-redis` and `... --profile redis-password run --rm test-redis-password`. Append a pytest command to narrow a run (`... run --rm test pytest tests/test_api_routes.py`), and run `docker compose -f compose.test.yml down -v` before switching setups. `export COMPOSE_FILE=compose.test.yml` shortens it to `docker compose run --rm test`.

Only one test session can run per dev container at a time: the tests bind ports 80, 443 and 8080 and stop every `nginx` process when they start Ceryx.

## Backend targeting

One pytest process targets one storage backend, selected by `CERYX_STORAGE_BACKEND`. Every run collects the same test node IDs, so CI reports one row per test across the backend columns.

- `redis`: all default tests run.
- `sqlite`: Redis-only assertions skip at runtime inside the test body.

Do not add parallel `Test*Redis` and `Test*SQLite` classes or select by backend marker. Add one test and let the matrix run it once per backend.

The `[tool.pytest]` table in `pyproject.toml` excludes `lets_encrypt` by default because ACME tests need public DNS and external network access. Run them against Let's Encrypt staging, with a domain that resolves publicly to this Ceryx on ports 80 and 443:

```bash
CERYX_LE_STAGING_DOMAIN=example.com pytest -m lets_encrypt
```

## API contract

`test_openapi.py` checks the API against `docs/openapi.yaml`, read from `CERYX_TEST_OPENAPI_SPEC` (default: `docs/openapi.yaml` in the checkout under test). When you change the API, change the spec too; the contract tests fail on undocumented statuses, methods or response bodies, and on documented responses no scenario produces.

## Targeting variables

| Variable | Purpose |
|---|---|
| `CERYX_STORAGE_BACKEND` | Backend for this pytest process |
| `CERYX_HOST` | Host for proxy and TLS requests |
| `CERYX_TEST_API_URL` | API origin |
| `CERYX_REDIS_HOST` | Redis host for direct Redis assertions |
| `CERYX_REDIS_PASSWORD` | Password of that Redis, if it requires one (the test stack's `redis-password` profile: `ceryx`) |
| `CERYX_TEST_SQLITE_PATH` | SQLite database the tests start Ceryx with and assert on (default: `/var/lib/ceryx/test.db`, separate from the app's `CERYX_SQLITE_PATH`) |
| `CERYX_TEST_AUTO_START` | `false` to use an already running Ceryx (Compose) |
| `CERYX_TEST_LETS_ENCRYPT_HOST` | Host of a running Ceryx with Let's Encrypt enabled, for the tests that need one (Compose: `ceryx-lets-encrypt`). Without it, the tests restart their own Ceryx with Let's Encrypt enabled for those tests. |
| `CERYX_TEST_ROOT`, `CERYX_TEST_NGINX_BIN` | Overrides for the checkout's `src/` and the NGINX binary (defaults: the checkout the tests live in, `nginx`). The tests render `src/templates` into a temporary directory, never into the checkout. |

Path variables (`CERYX_TEST_ROOT`, `CERYX_TEST_SQLITE_PATH`, `CERYX_TEST_OPENAPI_SPEC`) resolve relative values against the checkout the tests live in, and treat an empty value as unset.

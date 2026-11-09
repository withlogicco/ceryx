# Ceryx

**Rock-solid, fast, programmable gateway to your network services.**

Ceryx is a rock-solid, blazing fast, programmable HTTP/S gateway, running in a single container, programmable with an API, supporting tens of thousands of routes (domain-based proxying or redirecting).

[Quick start](#quick-start) · [API](#api) · [Production](#running-in-production) · [Settings](#settings)

## Simple architecture

- One container
- Straight forward JSON API over HTTP
- Real time configuration updates without restarts

## Features

- Host-based routing for HTTP and HTTPS
- Per-route settings
- Automatic Let's Encrypt certificates, or your own
- Client certificate authentication (mTLS)
- HTTP/2 and WebSockets

## Quick start

First, start Ceryx and a sample `echo` service on your machine:

```bash
docker compose -f 'https://github.com/withlogicco/ceryx.git#v1.0.0:docs/compose.example.yml' up -d
```

> [!TIP]
> 
> Ports 80, 443 or 8080 already in use? Pick others with `CERYX_EXTERNAL_HTTP_PORT`, `CERYX_EXTERNAL_HTTPS_PORT` and `CERYX_EXTERNAL_API_PORT`. Example:
> 
> ```
> CERYX_EXTERNAL_HTTP_PORT=8000 docker compose -f 'https://github.com/withlogicco/ceryx.git#v1.0.0:docs/compose.example.yml' up -d
> ```

Then, route `echo.localhost` to the `echo` service:

```bash
docker compose -p ceryx-example-echo exec ceryx curl -X POST localhost:8080/api/routes -H 'Content-Type: application/json' \
  -d '{"source": "echo.localhost", "target": "http://echo:5678"}'
```

Finally, check the result:

```console
$ curl http://echo.localhost
Hello from behind Ceryx
```

### Notes
- `*.localhost` points to your machine, so this works without DNS
- Clean up with `docker compose -p ceryx-example-echo down -v`
- To serve a real domain see [Running in production](#running-in-production).

## API

The most prominent use of the API is to add a new route. Example from hostname `app.example.com` to the target `app`:

```bash
docker compose -p ceryx exec ceryx curl -X POST localhost:8080/api/routes -H 'Content-Type: application/json' \
  -d '{"source": "app.example.com", "target": "http://app:8000"}'
```

See the full API feature set at [ceryx.dev/docs/api/](https://ceryx.dev/docs/api/).

## Running in production

On your server, start Ceryx with:

```bash
docker compose -f 'https://github.com/withlogicco/ceryx.git#v1.0.0:compose.yml' up -d
```

> [!TIP]
> 
> `compose.yml` respects `CERYX_EXTERNAL_HTTP_PORT`, `CERYX_EXTERNAL_HTTPS_PORT` for setting custom HTTP and HTTPS ports of the host for Ceryx to bind to.

See more advanced deployment options and configuration at [ceryx.dev/docs/deploy/](https://ceryx.dev/docs/deploy/).

## Settings

Ceryx is configured with environment variables.

| Variable | Default | Purpose |
|---|---|---|
| `CERYX_DISABLE_LETS_ENCRYPT` | `false` | Set to `true` to stop getting Let's Encrypt certificates automatically. |
| `CERYX_LETS_ENCRYPT_CA` | `https://acme-v02.api.letsencrypt.org/directory` | ACME directory URL, e.g. Let's Encrypt staging for testing. |
| `CERYX_SQLITE_PATH` | `/var/lib/ceryx/db.sqlite` | SQLite database file. |
| `CERYX_TLS_DEFAULT_CERTIFICATE` | `/etc/ceryx/ssl/default.crt` | Certificate for hostnames without one (self-signed). Ceryx 0.x's `CERYX_SSL_DEFAULT_CERTIFICATE` still works. |
| `CERYX_TLS_DEFAULT_KEY` | `/etc/ceryx/ssl/default.key` | Private key of the default certificate. Ceryx 0.x's `CERYX_SSL_DEFAULT_KEY` still works. |
| `CERYX_MAX_REQUEST_BODY_SIZE` | `100m` | Largest request body Ceryx accepts. |
| `CERYX_DNS_RESOLVER` | `127.0.0.11` | DNS server for resolving targets (Docker's by default). |
| `CERYX_DEBUG` | `false` | Turns on debug logs and turns off the Lua code cache. Development only. |

See all settings at [ceryx.dev/docs/settings/](https://ceryx.dev/docs/settings/).

> [!NOTE]
> Ceryx also has a Redis storage backend. It exists only to support pre-release versions of Ceryx and will be removed in the next major version.

## Development

Open the repository in its dev container to work on Ceryx.

## Testing

Run `docker compose -f compose.test.yml run --rm test`.

## License

[MIT](LICENSE)

# Ceryx - Rock-solid, programmable HTTP(S) reverse proxy

[![Build Status](https://travis-ci.org/sourcelair/ceryx.svg)](https://travis-ci.org/sourcelair/ceryx)

Ceryx is the rock-solid, programmable reverse proxy used to provide tens of thousands of [SourceLair](https://www.sourcelair.com/) projects with their unique HTTPS-enabled public URLs.

## High-level architecture

One of the main traits of Ceryx that makes it rock-solid is the simplicity in its design. Ceryx is comprised of two components and a Redis backend: the HTTP(S) reverse proxy and an API.

### Proxy
Ceryx uses NGINX OpenResty under the hood to route requests, based on the HTTP request's `Host` header or the [Server Name Indication](https://en.wikipedia.org/wiki/Server_Name_Indication) in HTTPS requests. Ceryx queries the Redis backend to decide to which target it should route each request.

### API
The Ceryx API lets users dynamically create, update and delete Ceryx routes via any HTTP client. The API essentially validates, sanitizes and eventually stores input in the Ceryx backend, to be queried by the proxy.

## Configuration

Ceryx is configured with the following environment variables:

  - `CERYX_API_HOST`: The host to bind the Ceryx API (default: `127.0.0.1`)
  - `CERYX_API_HOSTNAME`: Optional publicly accessible hostname for the Ceryx API (default: None)
  - `CERYX_API_PORT`: The port to bind the Ceryx API (default: `5555`)
  - `CERYX_DEBUG`: Enable debug logs for Ceryx API (default: `true`)
  - `CERYX_DISABLE_LETS_ENCRYPT`: Disable automatic Let's Encrypt HTTPS certificate generation (default: `false`)
  - `CERYX_DNS_RESOLVER`: The IP of the DNS resolver to use (default: `127.0.0.11` — the Docker DNS resolver)
  - `CERYX_DOCKERIZE_EXTRA_ARGS`: Extra arguments, to pass to `dockerize` (default: None)
  - `CERYX_MAX_REQUEST_BODY_SIZE`: The maximum body size allowed for an incoming request to Ceryx (default: `100m` — 100 megabytes)
  - `CERYX_REDIS_HOST`: The Redis host to use as backend (default: `127.0.0.1`)
  - `CERYX_REDIS_PASSWORD`: Optional password to use for authenticating with Redis (default: None)
  - `CERYX_REDIS_PORT`: The where Redis should be reached (default: `6379`)
  - `CERYX_REDIS_PREFIX`: The prefix to use in Ceryx-related Redis keys (default: `ceryx`)
  - `CERYX_REDIS_TIMEOUT`: The timeout for all Redis operations, including the intial connection to Redis, specified in milliseconds (default: `100`)
  - `CERYX_SSL_DEFAULT_CERTIFICATE`: The path to the fallback SSL certificate (default: `/etc/ceryx/ssl/default.crt` — randomly generated at build time)
  - `CERYX_SSL_DEFAULT_KEY`: The path to the fallback SSL certificate key (default: `/etc/ceryx/ssl/default.key` — randomly generated at build time)

## Adjusting log level

Ceryx will output logs of level to equal or higher of `info` by default. Setting `CERYX_DEBUG` to `true` will also output logs of `debug` level.

### Not running Ceryx as container?

👋 **Heads up!** Ceryx is designed to be run inside a container using Docker or similar tools. 

If you're not running Ceryx using the official [`sourcelair/ceryx`](https://hub.docker.com/r/sourcelair/ceryx/) image, you'll need to take care of configuration file generation yourself. Take a look at [`entrypoint.sh`](ceryx/bin/entrypoint.sh) to get ideas.

### Dynamic SSL certificates

By default, Ceryx will try to generate a certificate when a domain is hit via HTTPS through Let's Encrypt, if and only if a route exists for it. To disable this behavior, set `CERYX_DISABLE_LETS_ENCRYPT` to `true`.

## Quick start

You can start using Ceryx in a few seconds!

### Requirements

Before getting started, make sure you have the following:

1. A computer accessible from the internet with Docker ([docs](https://docs.docker.com/install/linux/docker-ce/ubuntu/)) and Docker Compose ([docs](https://docs.docker.com/compose/install/))
2. At least one domain (or subdomain) resolving to the computer's public IP addtess

### Running Ceryx

Just run the following command to run Ceryx in the background:

```
docker-compose up -d
```

### Running Ceryx in Kubernetes ###

#### Kubernetes Requirements ####
1. A Kubernetes cluster deployed with a public facing IP. Kubectl, Helm installed on your machine. Tiller installed on the cluster.  

2. At least one domain/subdomain (or even a wildcard A record) resolving to the cluster IP address.  

3. Edit the values file in .k8s/ceryx/values.yaml to suit your deployment needs.

4. 
```
cd k8s

helm install --debug --generate-name --values <path to your value file> ./ceryx

Recommend: Add --dry-run to the above before deploying to check generated yaml. 

```

### Exposing the API to the public

**👋 Heads up!** Don't ever do this in production! Anyone from the internet will be able to access the Ceryx API and mess with it. It's useful for development/testing though.

To access (and therefore 🐶 dogfood) the Ceryx API via Ceryx' proxy, set the `CERYX_API_HOSTNAME` setting and run the following command in your terminal:

```
docker-compose exec api bin/populate-api
```

## The Ceryx API

### Add a new route to Ceryx

```
curl -H "Content-Type: application/json" \
     -X POST \
     -d '{"source":"publicly.accessible.domain","target":"http://service.internal:8000"}' \
     http://ceryx-api-host/api/routes
```

### Update a route in Ceryx

```
curl -H "Content-Type: application/json" \
     -X PUT \
     -d '{"source":"publicly.accessible.domain","target":"http://another-service.internal:8000"}' \
     http://ceryx-api-host/api/routes/publicly.accessible.domain
```

### Delete a route from Ceryx

```
curl -H "Content-Type: application/json" \
     -X DELETE \
     http://ceryx-api-host/api/routes/publicly.accessible.domain
```

### Enforce HTTPS

You can enforce redirection from HTTP to HTTPS for any host you would like.

```
curl -H "Content-Type: application/json" \
     -X POST \
     -d '{"source":"publicly.accessible.domain","target":"http://service.internal:8000", "settings": {"enforce_https": true}}' \
     http://ceryx-api-host/api/routes
```

The above functionality works in `PUT` update requests as well.

### Redirect to target, instead of proxying

Instead of proxying the request to the targetm you can prompt the client to redirect the request there itself.

```
curl -H "Content-Type: application/json" \
     -X POST \
     -d '{"source":"sourcelair.com","target":"https://www.sourcelair.com", "settings": {"mode": "redirect"}}' \
     http://ceryx-api-host/api/routes
```

## Ceryx web UI

The [Ceryx Web community project](https://github.com/parisk/ceryx-web) provides a sweet web UI 

## Real-world uses

Ceryx has proven to be extremely reliable in production systems, handling tens of thousands of routes in its backend. Some of them are:

- [**SourceLair**](https://www.sourcelair.com/): In-browser IDE for web applications, made publicly accessible via development web servers powered by Ceryx.
- [**Stolos**](http://stolos.io/): Managed Docker development environments for enterprises.

Do you use Ceryx in production as well? Please [open a Pull Request](https://github.com/sourcelair/ceryx/pulls) to include it here. We would love to have it in our list.

## Origin

Ceryx started in [SourceLair](https://www.sourcelair.com) to help provide tens of thousands of users with a unique public URL (subdomain) for each one of their projects. Initial development had different stages; from using [tproxy](https://github.com/benoitc/tproxy), [Twisted](https://www.twistedmatrix.com/trac/) and bare [NGINX](https://nginx.org/en/) as a proxy and backends ranging from [MongoDB](https://www.mongodb.com/) to [etcd](https://github.com/etcd-io/etcd).

After a lot of experimentation, we have ended up in using [OpenResty](https://openresty.org/en/) as the proxy and [Redis](https://redis.io/) as the backend. This solution has served us and we are now developing it in the open as an open source project.

## License

Ceryx is [MIT licensed](LICENSE).

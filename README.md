# Ceryx - Simple, but powerful Reverse Proxy

[![Build Status](https://travis-ci.org/sourcelair/ceryx.svg)](https://travis-ci.org/sourcelair/ceryx)

Ceryx is a dynamic reverse proxy based on NGINX OpenResty with an API.

Ceryx is used to provide public URLs to tens of thousands of projects at https://www.sourcelair.com.

## Proxy
Ceryx is using NGINX OpenResty under the hood, in order to route requests
based on the request host. The routing is made using the NGINX Lua module,
which is querying a Redis backend for results.

## API
Ceryx comes with a simple Flask web service, which supports REST operations on
routes. You can dynamically create, update, and delete routes on the go using
a REST client.

## Configuration
Ceryx supports configuration using environment variables. The supported
configuration options are the following:

  * ``CERYX_API_HOST``: sets the host that the API will bind to - defaults to 127.0.0.1
  * ``CERYX_API_HOSTNAME``: identical to `CERYX_SERVER_NAME`, but without imposing `Host` header limits - default to None
  * ``CERYX_API_PORT``: sets the port that the API will listen - defaults to 5555
  * ``CERYX_DEBUG``: enables debugging on the API service - defaults to true
  * ``CERYX_DISABLE_LETS_ENCRYPT``: if true, the automatic generation through Let's Encrypt does not kick in, defaults to false
  * ``CERYX_DNS_RESOLVER``: the IP of the DNS resolver to use, defaults to 127.0.0.11 — the Docker DNS resolver
  * ``CERYX_DOCKERIZE_EXTRA_ARGS``: extra arguments, to pass to `dockerize`
  * ``CERYX_NAME``: sets the API service name - defaults to ceryx
  * ``CERYX_REDIS_HOST``: the redis host to connect to - defaults to 127.0.0.1
  * ``CERYX_REDIS_PASSWORD``: the redis password to use - defaults to none
  * ``CERYX_REDIS_PORT``: the redis port to connect to - defaults to 6379
  * ``CERYX_REDIS_PREFIX``: the redis prefix to use in keys - defaults to ceryx
  * ``CERYX_SECRET_KEY``: the path of the secret key to use - defaults to None
  * ``CERYX_SERVER_NAME``: the URL of the API service - default to None
  * ``CERYX_SSL_CERT_KEY``: the path to the SSL certificate key to use as fallback, defaults to a randomly generated key
  * ``CERYX_SSL_CERT``: the path to the SSL certificate to use as fallback, defaults to a randomly generated certificate

If you're not using the [`sourcelair/ceryx`](https://hub.docker.com/r/sourcelair/ceryx/) image, you'll need to use a command similar to the one below, to generate the configuration files needed from the environment, using [`dockerize`](https://github.com/jwilder/dockerize), through the [`entrypoint.sh`](ceryx/bin/entrypoint.sh) script.

```bash
bash ceryx/nginx/entrypoint.sh /usr/local/openresty/bin/openresty -g "daemon off;"
```

## Quick Bootstrap
Ceryx loves Docker, so you can easily bootstrap Ceryx using the following
command, given that you have already installed Docker and Docker Compose.

```
docker-compose up
```

To access (and therefore 🐶 dogfood 🐶) the Ceryx API via Ceryx' proxy, set the
`CERYX_API_HOSTNAME` environment variable and run the following command in your terminal:

```
docker-compose exec api bin/populate-api
```

## Development

Ceryx was developed as a private project for SourceLair PC. Initial development
had different stages, having tproxy, Twisted and plain NGINX as a proxy server
and backends ranging from MongoDB to etcd.

After a lot of experimentation, we have ended up in this solution and we'll
keep developing this as an Open Source project. Feel free to make suggestions
in the [issues section](https://github.com/sourcelair/ceryx/issues) in Github
or open o pull request.

## Dynamic SSL certificates

By default, Ceryx will try to generate a certificate when a domain is hit via HTTPS through Let's Encrypt, if and only if a route exists for it. If you don't want this to be enabled, you can use the `CERYX_DISABLE_LETS_ENCRYPT` setting.

## License

Ceryx is licensed under the "The MIT License (MIT)".

The MIT License (MIT)

Copyright (c) 2015 SourceLair PC

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

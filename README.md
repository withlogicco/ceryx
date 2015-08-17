# Ceryx - Simple, but powerful Reverse Proxy
Ceryx is a Dynamic reverse proxy based on NGINX OpenResty with an API.

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

  * ``CERYX_NAME``: sets the API service name - defaults to ceryx
  * ``CERYX_DEBUG``: enables debuging on the API service - defaults to true
  * ``CERYX_API_HOST``: sets the host that the API will bind to - defaults to 127.0.0.1
  * ``CERYX_API_PORT``: sets the port that the API will listen - defaults to 5555
  * ``CERYX_SERVER_NAME``: the URL of the API service - default to None
  * ``CERYX_SECRET_KEY``: the path of the secret key to use - defaults to None
  * ``CERYX_REDIS_HOST``: the redis host to connect to - defaults to 127.0.0.1
  * ``CERYX_REDIS_PORT``: the redis port to connect to - defaults to 6379
  * ``CERYX_REDIS_PREFIX``: the redis prefix to use in keys - defaults to ceryx

## Quick Bootstrap
Ceryx loves Docker, so you can easilly bootstrap Ceryx using the following
command, given that you have already installed Docker and Docker Compose.

```
docker-compose up
```

You can also easily create your own production Docker compose file, using the
services defined in base.yml file. An example Docker compose file could be the
following:

```yaml
# production.yml
proxy:
  extends:
    file: base.yml
    service: proxy
  ports:
   - "80:80"
  environment:
   - CERYX_REDIS_HOST=my.redis.host
api:
  extends:
    file: base.yml
    service: api
  ports:
   - "5555:5555"
  environment:
   - CERYX_REDIS_HOST=my.redis.host
   - CERYX_DEBUG=false
   - CERYX_SECRET_KEY=/path/to/production/secret
```

If you'd like to persist data, you can create the following file:

```yaml
# dev.yml
proxy:
  extends:
    file: base.yml
    service: proxy
  build: proxy
  ports:
   - "8888:80"
   - "5555:5555"
  volumes:
   - proxy/nginx/conf:/opt/openresty/nginx/conf
   - proxy/nginx/lualib:/opt/openresty/nginx/lualib
   - proxy/nginx/sites-enabled:/opt/openresty/nginx/sites-enabled
   - proxy/nginx/sites-available:/opt/openresty/nginx/sites-available
api:
  extends:
    file: base.yml
    service: api
  build: api
  net: container:proxy
  volumes:
   - api/ceryx:/ceryx/ceryx
   - api/bin:/ceryx/bin
redis:
  image: redis
  net: container:proxy
  volumes:
   - data:/data
  command: redis-server --appendonly yes
```

The above Redis container will store data in the data directory of your
project.

## Development

Ceryx was developed as a private project for SourceLair PC. Initial development
had different stages, having tproxy, Twisted and plain NGINX as a proxy server
and backends ranging from MongoDB to etcd.

After a lot of experimentation, we have ended up in this solution and we'll
keep developing this as an Open Source project. Feel free to make suggestions
in the [issues section](https://github.com/sourcelair/ceryx/issues) in Github
or open o pull request.

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

# Setting up dynamic SSL certificates with Let's encrypt

[Let's encrypt](https://letsencrypt.org/) is a free, automated, and open Certificate Authority.

This means that we can generate such certificates dynamically, each time a new HTTPS domain hits Ceryx. To do so, we'll use the great `[lua-resty-auto-ssl](https://github.com/GUI/lua-resty-auto-ssl)` library.

In order to make this work, your should use the `sourcelair/ceryx-proxy:dynamic-ssl` image flavor and define the following evnrironment variables:

* `CERYX_SSL_PATTERN` - Ceryx will check against this pattern before authorizing a new certificate. This could be something like `^subdomain.example.com$` for an exact domain, or `example.com$` for more than one subdomain. Note that this will still allow things like `heyexample.com`, but it's probably not worth the ugliness.

An example `docker-compose.yaml` file for this would be:

```yaml
version: '2'

services:
  proxy:
    image: sourcelair/ceryx-proxy:dynamic-ssl
    ports:
      - 80:80
      - 443:443
    environment:
      - CERYX_REDIS_HOST=redis
      - CERYX_REDIS_PORT=6379
      - CERYX_SSL_PATTERN=example.com$
      - CERYX_FALLBACK=www.something.com
    restart: always

    ...
```

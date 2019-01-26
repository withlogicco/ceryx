# Setting up dynamic SSL certificates with Let's encrypt

[Let's encrypt](https://letsencrypt.org/) is a free, automated, and open Certificate Authority.

This means that we can generate such certificates dynamically, each time a new HTTPS domain hits Ceryx. To do so, we'll use the great `[lua-resty-auto-ssl](https://github.com/GUI/lua-resty-auto-ssl)` library.

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
    restart: always

    ...
```

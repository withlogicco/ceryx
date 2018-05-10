#! /bin/bash

# Use Dockerize for templates and to wait for Redis
/usr/local/bin/dockerize \
    ${CERYX_DOCKERIZE_EXTRA_ARGS} \
    -template /usr/local/openresty/nginx/conf/nginx.conf.tmpl:/usr/local/openresty/nginx/conf/nginx.conf \
    -template  /usr/local/openresty/nginx/conf/ceryx.conf.tmpl:/usr/local/openresty/nginx/conf/ceryx.conf \
    -wait  tcp://${CERYX_REDIS_HOST:-redis}:${CERYX_REDIS_PORT:-6379}

# Execute subcommand
exec "$@"

#! /bin/bash

set -ex

if [ "$CERYX_DEBUG" == "true" ]
  then
    export CERYX_LOG_LEVEL=debug
  else
    export CERYX_LOG_LEVEL=info
fi

# Every file under CERYX_TEMPLATES_DIR renders to the same path under
# CERYX_CONFIG_ROOT: templates/nginx/api.conf -> /etc/nginx/api.conf.
CERYX_TEMPLATES_DIR=${CERYX_TEMPLATES_DIR:-/etc/ceryx/templates}
CERYX_CONFIG_ROOT=${CERYX_CONFIG_ROOT:-/etc}
AUTO_SSL_DIR=${CERYX_AUTO_SSL_DIR:-/var/lib/ceryx/auto-ssl}

CERYX_STORAGE_BACKEND=${CERYX_STORAGE_BACKEND:-sqlite}
DOCKERIZE_ARGS=(${CERYX_DOCKERIZE_EXTRA_ARGS})
while IFS= read -r -d '' template; do
    destination="${CERYX_CONFIG_ROOT}/${template#"${CERYX_TEMPLATES_DIR}"/}"
    mkdir -p "$(dirname "$destination")"
    DOCKERIZE_ARGS+=(-template "${template}:${destination}")
done < <(find "$CERYX_TEMPLATES_DIR" -type f -print0 | sort -z)

if [ "$CERYX_STORAGE_BACKEND" == "sqlite" ]; then
    echo "Using SQLite backend"
    # Ceryx creates the database schema itself (ceryx/backends/sqlite.lua);
    # NGINX workers only need to be able to write to the directory.
    CERYX_SQLITE_PATH=${CERYX_SQLITE_PATH:-/var/lib/ceryx/db.sqlite}
    CERYX_SQLITE_DIR=$(dirname "$CERYX_SQLITE_PATH")
    mkdir -p "$CERYX_SQLITE_DIR"
    chown -R www-data:www-data "$CERYX_SQLITE_DIR"
else
    echo "Using Redis backend"
    DOCKERIZE_ARGS+=(-wait "tcp://${CERYX_REDIS_HOST:-redis}:${CERYX_REDIS_PORT:-6379}")
fi

/usr/local/bin/dockerize "${DOCKERIZE_ARGS[@]}"

mkdir -p "$AUTO_SSL_DIR"
chown -R www-data:www-data "$AUTO_SSL_DIR"

# Execute subcommand
exec "$@"

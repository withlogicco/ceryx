FROM ubuntu:24.04 AS runtime

ARG DEBIAN_FRONTEND=noninteractive
ARG user=www-data
ARG group=www-data

RUN find /etc/apt \( -name '*.list' -o -name '*.sources' \) -type f -exec sed -i \
    -e 's|https://ports.ubuntu.com/ubuntu-ports|http://ports.ubuntu.com/ubuntu-ports|g' \
    -e 's|https://archive.ubuntu.com/ubuntu|http://archive.ubuntu.com/ubuntu|g' \
    -e 's|https://security.ubuntu.com/ubuntu|http://security.ubuntu.com/ubuntu|g' {} + || true

RUN --mount=type=bind,source=bin/install-luarocks.sh,target=/tmp/install-luarocks.sh \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    software-properties-common && \
    find /etc/apt \( -name '*.list' -o -name '*.sources' \) -type f -exec sed -i \
    -e 's|http://ports.ubuntu.com/ubuntu-ports|https://ports.ubuntu.com/ubuntu-ports|g' \
    -e 's|http://archive.ubuntu.com/ubuntu|https://archive.ubuntu.com/ubuntu|g' \
    -e 's|http://security.ubuntu.com/ubuntu|https://security.ubuntu.com/ubuntu|g' {} + && \
    add-apt-repository -y universe && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    git \
    libnginx-mod-http-lua \
    lua-cjson \
    lua-resty-core \
    lua-resty-lrucache \
    lua-nginx-redis \
    luajit2 \
    lua5.1 \
    liblua5.1-0-dev \
    luarocks \
    nginx \
    openssl \
    sqlite3 \
    libsqlite3-dev \
    build-essential \
    unzip \
    wget && \
    bash /tmp/install-luarocks.sh && \
    apt-get purge -y --auto-remove build-essential software-properties-common && \
    rm -rf /var/lib/apt/lists/* /tmp/luarocks_* /tmp/ceryx-luarocks-cache

# Static binary from the official multi-arch (amd64, arm64) image, pinned by
# digest. The image is merged-usr, so /bin/dockerize lives in /usr/bin.
COPY --link --from=ghcr.io/jwilder/dockerize:v0.16.0@sha256:89fc44b7cee99c8f68c9e895f6065e9b512594f368b774851b6dc639569b626f \
    /usr/bin/dockerize /usr/local/bin/dockerize

RUN mkdir -p /etc/ceryx/ssl /etc/ceryx/static /etc/nginx/sites-enabled /var/lib/ceryx /var/lib/ceryx/auto-ssl /usr/local/share/ceryx/lualib && \
    chown -R ${user}:${group} /var/lib/ceryx && \
    openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 \
    -subj '/CN=sni-support-required-for-valid-ssl' \
    -keyout /etc/ceryx/ssl/default.key \
    -out /etc/ceryx/ssl/default.crt

COPY src/templates /etc/ceryx/templates
COPY src/nginx/lualib /usr/local/share/ceryx/lualib
COPY src/static /etc/ceryx/static
COPY --chmod=755 bin/docker-entrypoint.sh /entrypoint.sh

# The entrypoint renders /etc/ceryx/templates into /etc; drop the package
# nginx.conf so it is rendered even with dockerize -no-overwrite.
RUN rm -f /etc/nginx/nginx.conf /etc/nginx/conf.d/default.conf /etc/nginx/sites-enabled/default

ENTRYPOINT ["/entrypoint.sh"]

ENV CERYX_STORAGE_BACKEND=sqlite \
    CERYX_SQLITE_PATH=/var/lib/ceryx/db.sqlite

CMD ["nginx", "-g", "daemon off;"]

FROM ghcr.io/withlogicco/python:3.12 AS test

ENV CERYX_DEBUG=true \
    CERYX_DISABLE_LETS_ENCRYPT=true \
    CERYX_STORAGE_BACKEND=sqlite

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl openssl && \
    mkdir -p /etc/ceryx/ssl && \
    openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 \
    -subj '/CN=sni-support-required-for-valid-ssl' \
    -keyout /etc/ceryx/ssl/default.key \
    -out /etc/ceryx/ssl/default.crt && \
    rm -rf /var/lib/apt/lists/*

# The uv cache mount makes a re-sync after a pyproject.toml-only change (for
# example pytest settings) a local copy. CI builders start with an empty
# cache mount; type=gha caches layers, not cache mounts.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=/usr/src/app/pyproject.toml \
    --mount=type=bind,source=uv.lock,target=/usr/src/app/uv.lock \
    uv sync --frozen

# pytest reads its settings from pyproject.toml.
COPY pyproject.toml ./
COPY tests ./tests
COPY docs/openapi.yaml ./docs/openapi.yaml

CMD ["pytest", "tests/"]

# The dev image's Python: a uv-managed (portable) interpreter and the venv
# built on it, both under /opt/uv, copied into the Ubuntu-based dev image.
FROM ghcr.io/withlogicco/python:3.12 AS venv

ENV UV_PYTHON_PREFERENCE=only-managed \
    UV_PYTHON_DOWNLOADS=manual \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python

RUN uv python install --no-bin 3.12
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=/usr/src/app/pyproject.toml \
    --mount=type=bind,source=uv.lock,target=/usr/src/app/uv.lock \
    uv sync --frozen

FROM runtime AS devcontainer

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    redis-tools \
    procps \
    iproute2 \
    less && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app

COPY --link --from=ghcr.io/withlogicco/python:3.12 /usr/local/bin/uv /usr/local/bin/uvx /usr/local/bin/
COPY --link --from=venv /opt/uv/python /opt/uv/python
COPY --link --from=venv /opt/uv/venv /opt/uv/venv

# Same uv settings as the venv stage, so uv sync in the dev container keeps
# using the copied interpreter and venv.
ARG UV_PROJECT_ENVIRONMENT=/opt/uv/venv
ENV PATH=${UV_PROJECT_ENVIRONMENT}/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_EDITABLE=1 \
    UV_NO_INSTALL_PROJECT=1 \
    UV_PROJECT_ENVIRONMENT=${UV_PROJECT_ENVIRONMENT} \
    UV_PYTHON_PREFERENCE=only-managed \
    UV_PYTHON_DOWNLOADS=manual \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    VIRTUAL_ENV=${UV_PROJECT_ENVIRONMENT} \
    VIRTUAL_ENV_PROMPT=''

FROM runtime AS final

#!/usr/bin/env bash

set -euo pipefail

lua_version="${LUA_VERSION:-5.1}"

install_rock() {
    luarocks --lua-version="${lua_version}" install "$@"
}

install_lua_resty_auto_ssl() {
    local version="0.13.1-1"
    local sockproc_sha="92aba736027bb5d96e190b71555857ac5bb6b2be"
    local sockproc_cache_dir="/tmp/ceryx-luarocks-cache/sockproc"
    local sockproc_tarball="${sockproc_cache_dir}/sockproc-${sockproc_sha}.tar.gz"
    local sockproc_checkout="${sockproc_cache_dir}/sockproc-${sockproc_sha}"
    local workdir

    mkdir -p "${sockproc_cache_dir}"
    workdir="$(mktemp -d)"
    trap 'rm -rf "${workdir}"' RETURN

    if [ ! -f "${sockproc_tarball}" ]; then
        rm -rf "${sockproc_checkout}"
        git clone --filter=blob:none https://github.com/juce/sockproc.git "${sockproc_checkout}"
        git -C "${sockproc_checkout}" checkout --detach "${sockproc_sha}"
        test "$(git -C "${sockproc_checkout}" rev-parse HEAD)" = "${sockproc_sha}"
        git -C "${sockproc_checkout}" archive \
            --format=tar.gz \
            --prefix="sockproc-${sockproc_sha}/" \
            -o "${sockproc_tarball}" \
            HEAD
    fi

    cd "${workdir}"
    luarocks --lua-version="${lua_version}" unpack lua-resty-auto-ssl "${version}"

    cd "${workdir}/lua-resty-auto-ssl-${version}/lua-resty-auto-ssl"

    # lua-resty-auto-ssl builds sockproc from a GitHub archive in its Makefile.
    # Docker builds can fail when GitHub redirects archive downloads to
    # codeload.github.com and that host is transiently unreachable. Keep the
    # same dependency/version, but pre-seed the exact archive and patch only the
    # download command to copy the cached archive instead of re-downloading it.
    sed -i \
        's|curl -sSLo sockproc-$(SOCKPROC_VERSION).tar.gz "https://github.com/juce/sockproc/archive/$(SOCKPROC_VERSION).tar.gz"|cp '"${sockproc_tarball}"' sockproc-$(SOCKPROC_VERSION).tar.gz|' \
        Makefile

    luarocks --lua-version="${lua_version}" make "lua-resty-auto-ssl-${version}.rockspec"
}

install_rock "https://raw.githubusercontent.com/fffonion/lua-resty-openssl/1.7.1/lua-resty-openssl-1.7.1-1.rockspec"
install_rock lua-resty-redis

# lua-resty-auto-ssl needs these OpenResty libraries without listing them,
# since OpenResty ships them; without them NGINX can't start with Let's Encrypt.
install_rock lua-resty-string 0.09-0
install_rock lua-resty-lock 0.09-1
install_lua_resty_auto_ssl

cd /tmp
install_rock lsqlite3

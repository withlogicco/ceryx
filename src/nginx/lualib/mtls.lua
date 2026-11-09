--[[
    Ceryx mTLS enforcement.

    During the TLS handshake, Ceryx asks for a client certificate only on
    hostnames whose route requires one, naming that route's CA
    (request_client_certificate, from certificate.lua).

    Every request is then checked against the route of its Host (enforce, from
    router.lua): plain HTTP is redirected to HTTPS, a request for another
    hostname than the TLS connection's gets 421 so the client retries on a
    connection of its own, and a missing or untrusted certificate gets 403.
]]

local mtls = require "ceryx.mtls"
local ngx_ssl = require "ngx.ssl"
local openssl_x509 = require "resty.openssl.x509"
local openssl_store = require "resty.openssl.x509.store"

local exports = {}

local CACHE_TTL = 5
local ca_store_cache = {}
local ca_handshake_cache = {}

local function is_blank(value)
    return value == nil or value == ngx.null or value == ""
end

local function read_file(path)
    local file = io.open(path, "r")
    if not file then
        return nil, "trusted CA bundle " .. path .. " is not readable"
    end

    local data = file:read("*a")
    file:close()
    return data
end

-- Cache by CA path (and depth) for a few seconds, so a replaced CA file is
-- picked up without a reload.
local function cached(cache, key, build)
    local now = ngx.now()
    local entry = cache[key]

    if entry and entry.expires_at > now then
        return entry.value
    end

    local value, err = build()
    if not value then
        return nil, err
    end

    cache[key] = {value = value, expires_at = now + CACHE_TTL}
    return value
end

local function ca_store(ca_path, verify_depth)
    return cached(ca_store_cache, ca_path .. ":" .. tostring(verify_depth), function()
        local store, err = openssl_store.new()
        if not store then
            return nil, err
        end

        local ok
        ok, err = store:load_file(ca_path)
        if not ok then
            return nil, err
        end

        if verify_depth ~= nil then
            ok, err = store:set_depth(verify_depth)
            if not ok then
                return nil, err
            end
        end

        return store
    end)
end

local function client_chain()
    local pem_chain = ngx.var.ssl_client_raw_cert

    if is_blank(pem_chain) and not is_blank(ngx.var.ssl_client_escaped_cert) then
        pem_chain = ngx.unescape_uri(ngx.var.ssl_client_escaped_cert)
    end

    if is_blank(pem_chain) then
        return nil, "no client certificate"
    end

    local certs = {}

    for pem in pem_chain:gmatch("%-%-%-%-%-BEGIN CERTIFICATE%-%-%-%-%-[^-]*%-%-%-%-%-END CERTIFICATE%-%-%-%-%-") do
        local cert, err = openssl_x509.new(pem, "PEM")
        if not cert then
            return nil, err
        end
        table.insert(certs, cert)
    end

    if #certs == 0 then
        return nil, "client certificate could not be parsed"
    end

    return certs
end

local function verify(certs, store)
    local chain

    if #certs > 1 then
        chain = require("resty.openssl.x509.chain").new()
        for index = 2, #certs do
            local ok, err = chain:add(certs[index])
            if not ok then
                return false, err
            end
        end
    end

    local ok, err = store:verify(certs[1], chain)
    if not ok then
        return false, err or "client certificate verification failed"
    end

    return true
end

-- Ceryx itself is misconfigured for this route: fail closed, with a 500.
local function misconfigured(reason)
    ngx.log(ngx.ERR, "mTLS: ", reason, " (route ", ngx.var.host, ")")
    return ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
end

local function forbidden(reason)
    ngx.log(ngx.WARN, "mTLS: ", reason, " for ", ngx.var.host)
    ngx.status = ngx.HTTP_FORBIDDEN
    ngx.say("client certificate required: " .. reason)
    return ngx.exit(ngx.HTTP_FORBIDDEN)
end

--- Ask for a client certificate in the TLS handshake for host, if its route
-- requires one. Runs in ssl_certificate_by_lua.
function exports.request_client_certificate(host)
    local policy = mtls.policy_for_host(host)

    if not policy.require_client_certificate then
        return
    end

    if policy.error or is_blank(policy.trusted_ca) then
        ngx.log(ngx.ERR, "mTLS: not asking for a client certificate for ", host, ": ",
            policy.error or "no trusted CA")
        return
    end

    local ca_certs, err = cached(ca_handshake_cache, policy.trusted_ca, function()
        local pem, read_err = read_file(policy.trusted_ca)
        if not pem then
            return nil, read_err
        end
        return ngx_ssl.parse_pem_cert(pem)
    end)

    if not ca_certs then
        ngx.log(ngx.ERR, "mTLS: could not load the trusted CA for ", host, ": ", err)
        return
    end

    local ok
    ok, err = ngx_ssl.verify_client(ca_certs, policy.verify_depth)
    if not ok then
        ngx.log(ngx.ERR, "mTLS: could not ask for a client certificate for ", host, ": ", err)
    end
end

--- Check the request against the route of its Host. Runs in access_by_lua.
function exports.enforce(host)
    local policy = mtls.policy_for_host(host)

    if not policy.require_client_certificate then
        return
    end

    if ngx.var.scheme ~= "https" then
        return ngx.redirect("https://" .. host .. ngx.var.request_uri, ngx.HTTP_MOVED_PERMANENTLY)
    end

    local server_name = ngx.var.ssl_server_name
    if not is_blank(server_name) and server_name:lower() ~= host:lower() then
        ngx.log(ngx.INFO, "mTLS: request for ", host, " on a TLS connection for ", server_name)
        return ngx.exit(421)
    end

    if policy.error then
        return misconfigured(policy.error)
    end

    if is_blank(policy.trusted_ca) then
        return misconfigured("no trusted CA: set mtls_trusted_ca or CERYX_MTLS_DEFAULT_TRUSTED_CA")
    end

    local certs, err = client_chain()
    if not certs then
        return forbidden(err)
    end

    local store
    store, err = ca_store(policy.trusted_ca, policy.verify_depth)
    if not store then
        return misconfigured("could not load the trusted CA " .. policy.trusted_ca .. ": " .. tostring(err))
    end

    local ok
    ok, err = verify(certs, store)
    if not ok then
        return forbidden(err)
    end
end

return exports

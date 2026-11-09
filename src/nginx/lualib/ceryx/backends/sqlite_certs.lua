--[[
    Ceryx SQLite Certificate Adapter for resty.auto-ssl

    Implements the resty.auto-ssl storage adapter interface using SQLite.
    Stores SSL certificates and related data in the resource table.

    Storage Format:
    - kind: 'certificate' for cert bundles, 'cert_data' for auto-ssl internal data
    - key: domain name or auto-ssl key
    - value: JWK bundle (cert + private_key + chain) or auto-ssl value
    - meta: JSON with vendor, issued_at, expires_at, san[], etc.

    JWK Bundle Format:
    {
        "certificate": "-----BEGIN CERTIFICATE-----...",
        "private_key": "-----BEGIN PRIVATE KEY-----...",
        "chain": "-----BEGIN CERTIFICATE-----..."
    }
]]

local utils = require "ceryx.utils"
local cjson = require "cjson"

-- Load SQLite backend
local SqliteBackend = require "ceryx.backends.sqlite"

local SqliteCertAdapter = {}
SqliteCertAdapter.__index = SqliteCertAdapter

-- Configuration
local DB_PATH = utils.getenv("CERYX_SQLITE_PATH", "/var/lib/ceryx/ceryx.db")

-- Shared backend instance
local _backend = nil

--- Get or create backend instance
local function get_backend()
    if not _backend then
        _backend = SqliteBackend.new()
        _backend:init()
    end
    return _backend
end

--- Create a new certificate adapter instance
-- This is called by resty.auto-ssl
-- @param options Optional configuration
-- @return adapter instance
function SqliteCertAdapter.new(options)
    local self = setmetatable({}, SqliteCertAdapter)
    self.options = options or {}
    return self
end

--- Get a value by key (resty.auto-ssl interface)
-- @param key The storage key
-- @return value string or nil
function SqliteCertAdapter:get(key)
    local backend = get_backend()

    -- Determine kind based on key pattern
    local kind = "cert_data" -- Default for auto-ssl internal data

    -- Check if this is a certificate bundle request
    if key:match(":latest$") or key:match(":fullchain%.pem$") or key:match(":privkey%.pem$") then
        -- These are auto-ssl internal keys
        kind = "cert_data"
    end

    local value, meta = backend:get(kind, key)

    if not value then
        ngx.log(ngx.DEBUG, "SQLite cert adapter: key not found: ", key)
        return nil
    end

    ngx.log(ngx.DEBUG, "SQLite cert adapter: got key: ", key)
    return value
end

--- Set a value by key (resty.auto-ssl interface)
-- @param key The storage key
-- @param value The value to store
-- @param options Optional settings (e.g., exptime)
-- @return boolean success
function SqliteCertAdapter:set(key, value, options)
    local backend = get_backend()
    options = options or {}

    -- Determine kind based on key pattern
    local kind = "cert_data"

    -- Build metadata
    local meta = {
        stored_at = os.date("!%Y-%m-%dT%H:%M:%SZ"),
        exptime = options.exptime
    }

    -- If this looks like a certificate, try to extract more metadata
    if value and value:match("BEGIN CERTIFICATE") then
        meta.type = "certificate"
    elseif value and value:match("BEGIN.*PRIVATE KEY") then
        meta.type = "private_key"
    end

    local ok = backend:set(kind, key, value, meta)

    if ok then
        ngx.log(ngx.DEBUG, "SQLite cert adapter: set key: ", key)
    else
        ngx.log(ngx.ERR, "SQLite cert adapter: failed to set key: ", key)
    end

    return ok
end

--- Delete a value by key (resty.auto-ssl interface)
-- @param key The storage key
-- @return boolean success
function SqliteCertAdapter:delete(key)
    local backend = get_backend()

    -- Try both kinds
    backend:delete("cert_data", key)
    backend:delete("certificate", key)

    ngx.log(ngx.DEBUG, "SQLite cert adapter: deleted key: ", key)
    return true
end

--- List keys ending with a suffix (resty.auto-ssl interface)
-- @param suffix The key suffix to match
-- @return array of matching keys
function SqliteCertAdapter:keys_with_suffix(suffix)
    local backend = get_backend()
    local records = backend:list("cert_data")
    local keys = {}

    for _, record in ipairs(records) do
        if record.key:sub(- #suffix) == suffix then
            table.insert(keys, record.key)
        end
    end

    return keys
end

--- Store a full certificate bundle for a domain
-- @param domain The domain name
-- @param cert_pem Certificate PEM string
-- @param key_pem Private key PEM string
-- @param chain_pem Optional certificate chain PEM
-- @param meta Optional metadata table
-- @return boolean success
function SqliteCertAdapter:store_certificate(domain, cert_pem, key_pem, chain_pem, meta)
    local backend = get_backend()

    -- Create JWK bundle
    local jwk_bundle = cjson.encode({
        certificate = cert_pem,
        private_key = key_pem,
        chain = chain_pem or ""
    })

    -- Build metadata
    meta = meta or {}
    meta.stored_at = os.date("!%Y-%m-%dT%H:%M:%SZ")
    meta.vendor = meta.vendor or "unknown"
    meta.type = meta.type or "manual"
    meta.auto_renew = meta.auto_renew or false

    -- Try to extract SAN from certificate
    if not meta.san then
        meta.san = { domain }
    end

    local ok = backend:set("certificate", domain, jwk_bundle, meta)

    if ok then
        ngx.log(ngx.INFO, "SQLite cert adapter: stored certificate for domain: ", domain)
    else
        ngx.log(ngx.ERR, "SQLite cert adapter: failed to store certificate for domain: ", domain)
    end

    return ok
end

--- Get a certificate bundle for a domain
-- @param domain The domain name
-- @return cert_pem, key_pem, chain_pem, meta or nil
function SqliteCertAdapter:get_certificate(domain)
    local backend = get_backend()

    local value, meta = backend:get("certificate", domain)

    if not value then
        -- Try wildcard
        local wildcard_domain = domain:match("^[^.]+%.(.+)$")
        if wildcard_domain then
            value, meta = backend:get("certificate", "*." .. wildcard_domain)
        end
    end

    if not value then
        return nil, nil, nil, nil
    end

    -- Parse JWK bundle
    local ok, bundle = pcall(cjson.decode, value)
    if not ok then
        ngx.log(ngx.ERR, "Failed to decode certificate bundle for domain: ", domain)
        return nil, nil, nil, nil
    end

    return bundle.certificate, bundle.private_key, bundle.chain, meta
end

--- Delete a certificate for a domain
-- @param domain The domain name
-- @return boolean success
function SqliteCertAdapter:delete_certificate(domain)
    local backend = get_backend()
    return backend:delete("certificate", domain)
end

--- List all stored certificates
-- @return array of {domain, meta}
function SqliteCertAdapter:list_certificates()
    local backend = get_backend()
    local records = backend:list("certificate")

    local results = {}
    for _, record in ipairs(records) do
        table.insert(results, {
            domain = record.key,
            meta = record.meta
        })
    end

    return results
end

--- Check if a certificate exists for a domain
-- @param domain The domain name
-- @return boolean
function SqliteCertAdapter:has_certificate(domain)
    local backend = get_backend()

    if backend:exists("certificate", domain) then
        return true
    end

    -- Check wildcard
    local wildcard_domain = domain:match("^[^.]+%.(.+)$")
    if wildcard_domain then
        return backend:exists("certificate", "*." .. wildcard_domain)
    end

    return false
end

--- Store Let's Encrypt account key
-- @param key_pem Account private key PEM
-- @return boolean success
function SqliteCertAdapter:store_account_key(key_pem)
    local backend = get_backend()

    local meta = {
        stored_at = os.date("!%Y-%m-%dT%H:%M:%SZ"),
        type = "account_key",
        vendor = "letsencrypt"
    }

    return backend:set("cert_data", "letsencrypt:account_key", key_pem, meta)
end

--- Get Let's Encrypt account key
-- @return key_pem or nil
function SqliteCertAdapter:get_account_key()
    local backend = get_backend()
    local value, _ = backend:get("cert_data", "letsencrypt:account_key")
    return value
end

--- Create the adapter factory function for resty.auto-ssl
-- @return adapter factory
function SqliteCertAdapter.create_adapter()
    return function(options)
        return SqliteCertAdapter.new(options)
    end
end

return SqliteCertAdapter

--[[
    Ceryx Storage Abstraction Layer
    
    Provides a unified interface for storage backends (Redis, SQLite).
    Backend selection is controlled by CERYX_STORAGE_BACKEND environment variable.
    
    Data Schema (resource table):
    - kind: string (e.g., 'route', 'certificate')
    - key: string (e.g., hostname, domain)
    - value: string (e.g., target URL, JWK certificate bundle)
    - meta: JSON string (e.g., settings, certificate metadata)
]]

local utils = require "ceryx.utils"
local cjson = require "cjson"

local exports = {}
local wildcard_source = "$wildcard"

local function is_valid_value(value)
    return value ~= nil and value ~= ngx.null and value ~= ""
end

local function normalize_enforce_https(value)
    if value == nil or value == ngx.null then
        return nil
    end

    if type(value) == "string" then
        return value == "true" or value == "1"
    end

    return value == true or value == 1
end

-- mTLS settings. mtls_require_client_certificate is always stored; the CA
-- and depth only when set.
local function copy_mtls_settings(settings, result)
    local require_client_certificate = normalize_enforce_https(settings.mtls_require_client_certificate)
    if require_client_certificate ~= nil and settings.mtls_require_client_certificate ~= "" then
        result.mtls_require_client_certificate = require_client_certificate
    end

    if is_valid_value(settings.mtls_trusted_ca) then
        result.mtls_trusted_ca = settings.mtls_trusted_ca
    end

    if is_valid_value(settings.mtls_verify_depth) then
        result.mtls_verify_depth = tonumber(settings.mtls_verify_depth)
    end
end

local function normalize_route_meta(meta)
    local result = {}

    if not meta then
        return result
    end

    copy_mtls_settings(meta, result)

    if meta.mode ~= nil and meta.mode ~= ngx.null and meta.mode ~= "" then
        result.mode = meta.mode
    end

    local enforce_https = normalize_enforce_https(meta.enforce_https)
    if enforce_https ~= nil then
        result.enforce_https = enforce_https
    end

    if meta.certificate_path ~= nil and meta.certificate_path ~= ngx.null and meta.certificate_path ~= "" then
        result.certificate_path = meta.certificate_path
    end

    if meta.key_path ~= nil and meta.key_path ~= ngx.null and meta.key_path ~= "" then
        result.key_path = meta.key_path
    end

    return result
end

local function normalize_route_target(value, meta)
    if meta and is_valid_value(meta.target) then
        return meta.target
    end

    if is_valid_value(value) then
        return value
    end

    return nil
end

local function normalize_settings_for_storage(settings)
    local result = {}

    if not settings then
        return result
    end

    copy_mtls_settings(settings, result)

    -- Stored even at their defaults, like every setting a route has.
    result.enforce_https = normalize_enforce_https(settings.enforce_https) == true

    if is_valid_value(settings.mode) then
        result.mode = settings.mode
    else
        result.mode = "proxy"
    end

    if settings.certificate_path ~= nil and settings.certificate_path ~= ngx.null and settings.certificate_path ~= "" then
        result.certificate_path = settings.certificate_path
    end

    if settings.key_path ~= nil and settings.key_path ~= ngx.null and settings.key_path ~= "" then
        result.key_path = settings.key_path
    end

    return result
end

-- Configuration
local STORAGE_BACKEND = utils.getenv("CERYX_STORAGE_BACKEND", "redis")

-- Backend cache
local _backend = nil
local _backend_initialized = false

--[[
    Storage Interface Methods:
    
    backend:get(kind, key) -> value, meta_table or nil
    backend:set(kind, key, value, meta_table) -> boolean
    backend:delete(kind, key) -> boolean
    backend:list(kind) -> array of {key, value, meta}
    backend:exists(kind, key) -> boolean
    backend:get_with_fallback(kind, key, fallback_key) -> value, meta_table or nil
]]

--- Load and initialize the configured storage backend
-- @return backend instance
local function load_backend()
    if _backend then
        return _backend
    end
    
    local backend_module
    
    if STORAGE_BACKEND == "sqlite" then
        backend_module = require "ceryx.backends.sqlite"
    elseif STORAGE_BACKEND == "redis" then
        backend_module = require "ceryx.backends.redis"
    else
        ngx.log(ngx.ERR, "Unknown storage backend: " .. STORAGE_BACKEND .. ", falling back to redis")
        backend_module = require "ceryx.backends.redis"
    end
    
    _backend = backend_module.new()

    if _backend.init and not _backend_initialized then
        local ok, result = pcall(function()
            return _backend:init()
        end)

        if not ok or result == false then
            ngx.log(ngx.ERR, "Failed to initialize storage backend: ", result or "unknown error")
        else
            _backend_initialized = true
        end
    else
        _backend_initialized = true
    end

    return _backend
end

--- Get the configured storage backend instance
-- @return backend instance
function exports.backend()
    return load_backend()
end

--- Get a route with automatic $wildcard fallback
-- @param source The source hostname
-- @return target, meta_table or nil
function exports.get_route(source, fallback_to_wildcard)
    local backend = load_backend()
    local value, meta = backend:get("route", source)
    local target = normalize_route_target(value, meta)
    
    if target then
        return target, normalize_route_meta(meta)
    end

    if not fallback_to_wildcard then
        return nil, nil
    end

    if source == wildcard_source then
        return nil, nil
    end

    value, meta = backend:get("route", wildcard_source)
    target = normalize_route_target(value, meta)

    if not target then
        -- Try wildcard fallback
        return nil, nil
    end
    
    return target, normalize_route_meta(meta)
end

--- Set a route with settings in meta
-- @param source The source hostname
-- @param target The target URL
-- @param settings Table with route settings (enforce_https, mode, etc.)
-- @return boolean
function exports.set_route(source, target, settings)
    local backend = load_backend()
    local meta = normalize_settings_for_storage(settings)

    if source == wildcard_source then
        return backend:set("route", source, target, meta)
    end

    meta.target = target

    return backend:set("route", source, "", meta)
end

--- Delete a route
-- @param source The source hostname
-- @return boolean
function exports.delete_route(source)
    local backend = load_backend()
    return backend:delete("route", source)
end

--- List all routes
-- @return array of {key=source, value=target, meta=settings}
function exports.list_routes()
    local backend = load_backend()
    local records = backend:list("route")
    local routes = {}

    for _, record in ipairs(records) do
        local target, meta = exports.get_route(record.key, false)

        if target then
            table.insert(routes, {
                key = record.key,
                value = target,
                meta = meta or {}
            })
        end
    end

    return routes
end

--- Get a certificate (JWK bundle with cert + private key)
-- @param domain The domain name
-- @param fallback_to_wildcard Try *.parent when there is no exact match (default true)
-- @return jwk_bundle, meta_table or nil
function exports.get_certificate(domain, fallback_to_wildcard)
    local backend = load_backend()
    local value, meta = backend:get("certificate", domain)
    
    if not value and fallback_to_wildcard ~= false then
        -- Try wildcard certificate matching
        -- e.g., for foo.example.com, try *.example.com
        local wildcard_domain = domain:match("^[^.]+%.(.+)$")
        if wildcard_domain then
            value, meta = backend:get("certificate", "*." .. wildcard_domain)
        end
    end
    
    return value, meta
end

--- Set a certificate (JWK bundle format)
-- @param domain The domain name
-- @param jwk_bundle JSON string with certificate, private_key, chain
-- @param meta Table with vendor, issued_at, expires_at, san[], etc.
-- @return boolean
function exports.set_certificate(domain, jwk_bundle, meta)
    local backend = load_backend()
    
    -- Ensure required meta fields
    meta = meta or {}
    meta.issued_at = meta.issued_at or os.date("!%Y-%m-%dT%H:%M:%SZ")
    
    return backend:set("certificate", domain, jwk_bundle, meta)
end

--- Delete a certificate
-- @param domain The domain name
-- @return boolean
function exports.delete_certificate(domain)
    local backend = load_backend()
    return backend:delete("certificate", domain)
end

--- List all certificates
-- @return array of {key=domain, value=jwk_bundle, meta=metadata}
function exports.list_certificates()
    local backend = load_backend()
    return backend:list("certificate")
end

--- Check if a certificate exists for a domain (including wildcard)
-- @param domain The domain name
-- @return boolean
function exports.has_certificate(domain)
    local backend = load_backend()
    
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

--- Get the name of the current storage backend
-- @return string ("redis" or "sqlite")
function exports.get_backend_name()
    return STORAGE_BACKEND
end

--- Initialize the storage backend (create tables, etc.)
-- Should be called once at startup
-- @return boolean
function exports.init()
    local backend = load_backend()
    if backend.init then
        return backend:init()
    end
    return true
end

--- Close/cleanup the storage backend
function exports.close()
    if _backend and _backend.close then
        _backend:close()
    end
    _backend = nil
    _backend_initialized = false
end

return exports

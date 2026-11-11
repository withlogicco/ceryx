--[[
    Ceryx Routes Module
    
    Handles route lookups and management using the storage abstraction layer.
    Supports both Redis and SQLite backends transparently.
    
    Routes are stored as:
    - kind: 'route'
    - key: source hostname
    - value: target URL
    - meta: {enforce_https, mode, certificate_path, key_path, mtls_*}
]]

local cjson = require "cjson"
local host_settings = require "ceryx.settings"
local storage = require "ceryx.storage"
local utils = require "ceryx.utils"

-- Legacy module for backward compatibility
local redis_ok, redis = pcall(require, "ceryx.redis")

local exports = {}
local STORAGE_BACKEND = utils.getenv("CERYX_STORAGE_BACKEND", "redis")
local SETTINGS_CACHE_FIELDS = {
    "target",
    "enforce_https",
    "mode",
    "certificate_path",
    "key_path",
    "mtls_require_client_certificate",
    "mtls_trusted_ca",
    "mtls_verify_depth"
}
local SETTING_FIELDS = {
    "enforce_https",
    "mode",
    "certificate_path",
    "key_path",
    "mtls_require_client_certificate",
    "mtls_trusted_ca",
    "mtls_verify_depth"
}

-- Default route settings
local DEFAULT_SETTINGS = {
    enforce_https = false,
    mode = "proxy",
    certificate_path = "",
    key_path = "",
    mtls_require_client_certificate = false,
    mtls_trusted_ca = "",
    mtls_verify_depth = ""
}

--- Legacy: Get route key for a source (backward compatibility)
function getRouteKeyForSource(source)
    if redis_ok then
        return redis.prefix .. ":routes:" .. source
    end
    return "ceryx:routes:" .. source
end

--- Legacy: Get settings key for a source (backward compatibility)
function getSettingsKeyForSource(source)
    if redis_ok then
        return redis.prefix .. ":settings:" .. source
    end
    return "ceryx:settings:" .. source
end

--- Construct settings with defaults
-- @param settings Input settings table
-- @param initSettings Optional initial settings
-- @return Complete settings table
function constructSettings(settings, initSettings)
    local result = {}
    
    -- Start with defaults
    for key, value in pairs(DEFAULT_SETTINGS) do
        result[key] = value
    end
    
    -- Apply initial settings if provided
    if initSettings and initSettings ~= ngx.null then
        for _, key in ipairs(SETTING_FIELDS) do
            local value = initSettings[key]
            if value ~= nil and value ~= ngx.null then
                result[key] = value
            end
        end
    end
    
    -- Apply input settings (override)
    if settings and settings ~= ngx.null then
        for _, key in ipairs(SETTING_FIELDS) do
            local value = settings[key]
            if value ~= nil and value ~= ngx.null then
                result[key] = value
            end
        end
    end
    
    return result
end

-- Defaults for the settings a new route doesn't pass, stored with it.
local CREATION_DEFAULTS = {
    enforce_https = "CERYX_ROUTE_SETTINGS_DEFAULT_ENFORCE_HTTPS",
    mtls_require_client_certificate = "CERYX_ROUTE_SETTINGS_DEFAULT_MTLS_REQUIRE_CLIENT_CERTIFICATE"
}

--- The settings of a route being created: settings, plus the
-- CERYX_ROUTE_SETTINGS_DEFAULT_* variables for those it doesn't pass.
-- @return settings, or nil and an error naming a variable that isn't true or false
function withCreationDefaults(settings)
    local result = {}

    if settings and settings ~= ngx.null then
        for key, value in pairs(settings) do
            result[key] = value
        end
    end

    for key, variable in pairs(CREATION_DEFAULTS) do
        local value = utils.getenv(variable, nil)
        if (result[key] == nil or result[key] == ngx.null) and value ~= nil then
            local lowered = value:lower()
            if lowered ~= "true" and lowered ~= "false" then
                return nil, variable .. " must be true or false, not '" .. value .. "'."
            end
            result[key] = lowered == "true"
        end
    end

    return result
end

--- Serialize settings for API response
-- @param settings Settings table
-- @return Serialized settings table
function serializeSettings(settings)
    local result = {}
    
    for _, key in ipairs(SETTING_FIELDS) do
        result[key] = settings[key]
    end
    
    -- Convert empty strings to null for JSON
    if result.certificate_path == "" then
        result.certificate_path = ngx.null
    end

    if result.key_path == "" then
        result.key_path = ngx.null
    end

    -- Ensure enforce_https is boolean
    if type(result.enforce_https) == "string" then
        result.enforce_https = result.enforce_https == "true" or result.enforce_https == "1"
    end

    -- Unset mTLS settings are null; stored values may be strings (Redis)
    if result.mtls_require_client_certificate == "" then
        result.mtls_require_client_certificate = ngx.null
    elseif type(result.mtls_require_client_certificate) == "string" then
        result.mtls_require_client_certificate = result.mtls_require_client_certificate == "true"
    end

    if result.mtls_trusted_ca == "" then
        result.mtls_trusted_ca = ngx.null
    end

    if result.mtls_verify_depth == "" then
        result.mtls_verify_depth = ngx.null
    else
        result.mtls_verify_depth = tonumber(result.mtls_verify_depth)
    end
    
    return result
end

--- Check if target is invalid
-- @param target Target value to check
-- @return boolean
function targetIsInValid(target)
    return not target or target == ngx.null or target == ""
end

local function getLegacyRouteTarget(source, redisClient)
    if STORAGE_BACKEND == "redis" and redis_ok then
        local client = redisClient or redis:client()
        local target, _ = client:get(getRouteKeyForSource(source))

        if target == ngx.null then
            return nil
        end

        return target
    end

    local backend = storage.backend()
    local target, _ = backend:get("route", source)

    if targetIsInValid(target) then
        return nil
    end

    return target
end

--- Get target URL for a source hostname (uses storage abstraction)
-- @param source The source hostname
-- @param redisClient Optional redis client (ignored, kept for backward compatibility)
-- @return target URL or nil
function getTargetForSource(source, redisClient)
    local target = host_settings.getSettingForHost(source, "target", false)

    if targetIsInValid(target) then
        ngx.log(ngx.INFO, "Could not find target setting for " .. source .. ".")
        target = getLegacyRouteTarget(source, redisClient)
    end

    if targetIsInValid(target) then
        ngx.log(ngx.INFO, "Could not find target for " .. source .. ".")
        target = getLegacyRouteTarget("$wildcard", redisClient)

        if targetIsInValid(target) then
            return nil
        end

        ngx.log(ngx.DEBUG, "Falling back to " .. target .. ".")
    end
    
    return target
end

--- Get routing mode for a source
-- @param source The source hostname
-- @param redisClient Optional redis client (ignored, kept for backward compatibility)
-- @return mode string ('proxy' or 'redirect')
function getModeForSource(source, redisClient)
    ngx.log(ngx.DEBUG, "Get routing mode for " .. source .. ".")
    
    local mode = host_settings.getSettingForHost(source, "mode", true)

    if mode == nil or mode == ngx.null or mode == "" then
        return "proxy"
    end
    
    return mode
end

--- Fetch and serialize a route for a source
-- @param source The source hostname
-- @param redisClient Optional redis client (ignored, kept for backward compatibility)
-- @return Route table {source, target, settings} or nil
function fetchAndSerializeRoute(source, redisClient)
    local target, meta = storage.get_route(source, false)
    
    if not target then
        return nil
    end
    
    local settings = constructSettings(meta)
    
    return {
        source = source,
        target = target,
        settings = serializeSettings(settings)
    }
end

--- Get route for source with caching
-- @param source The source hostname
-- @return Route table {target, mode} or nil
function getRouteForSource(source)
    local route = {}
    local cache = ngx.shared.ceryx
    local redisClient = nil

    if STORAGE_BACKEND == "redis" and redis_ok then
        redisClient = redis:client()
    end

    ngx.log(ngx.DEBUG, "Looking for a route for " .. source)
    
    -- Check if key exists in local cache
    local cached_value, _ = cache:get(source)

    if cached_value then
        ngx.log(ngx.DEBUG, "Cache hit for " .. source .. ".")
        route.target = cached_value
    else
        ngx.log(ngx.DEBUG, "Cache miss for " .. source .. ".")
        route.target = getTargetForSource(source, redisClient)

        if targetIsInValid(route.target) then
            return nil
        end
        
        -- Cache the target for 5 seconds
        cache:set(source, route.target, 5)
        ngx.log(ngx.DEBUG, "Caching from " .. source .. " to " .. route.target .. " for 5 seconds.")
    end

    route.mode = getModeForSource(source)

    return route
end

--- Get enforce_https setting for a source
-- @param source The source hostname
-- @return boolean
function getEnforceHttpsForSource(source)
    local enforce_https = host_settings.getSettingForHost(source, "enforce_https", true)

    if enforce_https == nil or enforce_https == ngx.null then
        return false
    end

    if type(enforce_https) == "string" then
        return enforce_https == "true" or enforce_https == "1"
    end

    return enforce_https == true or enforce_https == 1
end

--- Create or update a route
-- @param source The source hostname
-- @param target The target URL
-- @param settings Optional settings table
-- @return boolean success
function setRoute(source, target, settings)
    settings = constructSettings(settings)
    local cache = ngx.shared.ceryx

    cache:delete(source)
    host_settings.clearCacheForHost(source, SETTINGS_CACHE_FIELDS)

    return storage.set_route(source, target, settings)
end

--- Delete a route
-- @param source The source hostname
-- @return boolean success
function deleteRoute(source)
    -- Clear from cache first
    local cache = ngx.shared.ceryx
    cache:delete(source)
    host_settings.clearCacheForHost(source, SETTINGS_CACHE_FIELDS)
    
    return storage.delete_route(source)
end

--- List all routes
-- @return Array of route tables
function listRoutes()
    local records = storage.list_routes()
    local routes = {}
    
    for _, record in ipairs(records) do
        table.insert(routes, {
            source = record.key,
            target = record.value,
            settings = serializeSettings(constructSettings(record.meta))
        })
    end
    
    return routes
end

-- Exports
exports.getSettingsKeyForSource = getSettingsKeyForSource
exports.getRouteKeyForSource = getRouteKeyForSource
exports.fetchAndSerializeRoute = fetchAndSerializeRoute
exports.getRouteForSource = getRouteForSource
exports.getTargetForSource = getTargetForSource
exports.getModeForSource = getModeForSource
exports.getEnforceHttpsForSource = getEnforceHttpsForSource
exports.constructSettings = constructSettings
exports.withCreationDefaults = withCreationDefaults
exports.serializeSettings = serializeSettings
exports.setRoute = setRoute
exports.deleteRoute = deleteRoute
exports.listRoutes = listRoutes

return exports

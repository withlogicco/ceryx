local utils = require "ceryx.utils"
local storage = require "ceryx.storage"

local STORAGE_BACKEND = utils.getenv("CERYX_STORAGE_BACKEND", "redis")
local wildcard_host = "$wildcard"
local settings_cache_ttl = 5
local cache_nil_value = "__nil__"

local exports = {}

local redis_ok, redis = pcall(require, "ceryx.redis")

local function getCacheKeyForHost(host, field)
    return "settings:" .. host .. ":" .. field
end

local function toCacheValue(value)
    if value == nil then
        return cache_nil_value
    end

    return value
end

local function fromCacheValue(value)
    if value == cache_nil_value then
        return nil
    end

    return value
end

local function hasAnySetting(settings, fields)
    if settings == nil then
        return false
    end

    for _, field in ipairs(fields) do
        if settings[field] ~= nil then
            return true
        end
    end

    return false
end

local function cacheSettingsForHost(cache, host, fields, settings)
    for _, field in ipairs(fields) do
        local cache_key = getCacheKeyForHost(host, field)
        cache:set(cache_key, toCacheValue(settings[field]), settings_cache_ttl)
    end
end

local function getCachedSettingsForHost(cache, host, fields)
    local settings = {}

    for _, field in ipairs(fields) do
        local cache_key = getCacheKeyForHost(host, field)
        local value = cache:get(cache_key)

        if value == nil then
            return nil
        end

        settings[field] = fromCacheValue(value)
    end

    ngx.log(ngx.DEBUG, "Settings cache hit for " .. host .. ".")
    return settings
end

local function readSettingsFromRedis(host, fields, cache)
    local cached_settings = getCachedSettingsForHost(cache, host, fields)
    if cached_settings ~= nil then
        return cached_settings
    end

    ngx.log(ngx.DEBUG, "Settings cache miss for " .. host .. ".")

    local redisClient = redis:client()
    local redis_key = exports.getRedisKeyForHost(host)
    local values, err = redisClient:hmget(redis_key, unpack(fields))

    if err then
        ngx.log(ngx.ERR, "Could not retrieve settings for " .. host .. " from Redis: " .. err)
        return nil
    end

    local settings = {}

    for index, field in ipairs(fields) do
        local value = values[index]

        if value ~= ngx.null then
            settings[field] = value
        end
    end

    cacheSettingsForHost(cache, host, fields, settings)

    return settings
end

local function readSettingsFromStorage(host, fields, cache)
    local cached_settings = getCachedSettingsForHost(cache, host, fields)
    if cached_settings ~= nil then
        return cached_settings
    end

    ngx.log(ngx.DEBUG, "Settings cache miss for " .. host .. ".")

    local backend = storage.backend()
    local _, meta = backend:get("route", host)
    local settings = {}

    if meta then
        for _, field in ipairs(fields) do
            local value = meta[field]

            if value ~= nil and value ~= ngx.null then
                settings[field] = value
            end
        end
    end

    cacheSettingsForHost(cache, host, fields, settings)

    return settings
end

local function readSettingsForHost(host, fields, cache)
    if STORAGE_BACKEND == "redis" and redis_ok then
        return readSettingsFromRedis(host, fields, cache)
    end

    return readSettingsFromStorage(host, fields, cache)
end

function exports.getRedisKeyForHost(host)
    if redis_ok then
        return redis.prefix .. ":settings:" .. host
    end

    return "ceryx:settings:" .. host
end

-- Settings for host come only from its own route. With fallback_to_wildcard,
-- a host without a route of its own gets the $wildcard route's, since that
-- route serves it.
function exports.getSettingsForHost(host, fields, fallback_to_wildcard)
    local cache = ngx.shared.ceryx

    -- Routes other than $wildcard store their target with their settings,
    -- so it tells whether host has a route of its own.
    local wants_target = false
    for _, field in ipairs(fields) do
        if field == "target" then
            wants_target = true
        end
    end

    local lookup = fields
    if not wants_target then
        lookup = {"target", unpack(fields)}
    end

    local settings = readSettingsForHost(host, lookup, cache) or {}
    local has_route = host == wildcard_host or settings.target ~= nil

    if not wants_target then
        settings.target = nil
    end

    if has_route or hasAnySetting(settings, fields) then
        return settings
    end

    if not fallback_to_wildcard then
        return nil
    end

    ngx.log(ngx.DEBUG, "No route found for " .. host .. ".")

    settings = readSettingsForHost(wildcard_host, fields, cache)

    if not hasAnySetting(settings, fields) then
        ngx.log(ngx.DEBUG, "No settings found for fallback " .. wildcard_host .. ".")
        return nil
    end

    ngx.log(ngx.DEBUG, "Using settings from " .. wildcard_host .. " for " .. host .. ".")

    return settings
end

function exports.getSettingForHost(host, field, fallback_to_wildcard)
    local settings = exports.getSettingsForHost(host, {field}, fallback_to_wildcard)

    if settings == nil then
        return nil
    end

    return settings[field]
end

function exports.clearCacheForHost(host, fields)
    local cache = ngx.shared.ceryx

    for _, field in ipairs(fields) do
        cache:delete(getCacheKeyForHost(host, field))
    end
end

return exports
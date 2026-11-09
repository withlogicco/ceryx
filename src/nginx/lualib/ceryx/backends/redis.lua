--[[
    Ceryx Redis Storage Backend
    
    Implements the storage interface using Redis.
    Maintains backward compatibility with existing Ceryx Redis key patterns.
    
    Key Patterns:
    - Routes: {prefix}:routes:{source} -> target URL
    - Settings (legacy): {prefix}:settings:{source} -> hash of settings
    - New format stores settings in meta field as JSON
    
    Environment Variables:
    - CERYX_REDIS_PREFIX: Key prefix (default: ceryx)
    - CERYX_REDIS_HOST: Redis host (default: 127.0.0.1)
    - CERYX_REDIS_PORT: Redis port (default: 6379)
    - CERYX_REDIS_PASSWORD: Optional authentication
    - CERYX_REDIS_TIMEOUT: Connection timeout in ms (default: 100)
]]

local redis = require "resty.redis"
local utils = require "ceryx.utils"
local cjson = require "cjson"

local RedisBackend = {}
RedisBackend.__index = RedisBackend

local wildcard_source = "$wildcard"

-- Configuration from environment
local PREFIX = utils.getenv("CERYX_REDIS_PREFIX", "ceryx")
local HOST = utils.getenv("CERYX_REDIS_HOST", "127.0.0.1")
local PORT = tonumber(utils.getenv("CERYX_REDIS_PORT", "6379"))
local PASSWORD = utils.getenv("CERYX_REDIS_PASSWORD", nil)
local TIMEOUT = tonumber(utils.getenv("CERYX_REDIS_TIMEOUT", "100"))

--- Create a new Redis backend instance
-- @return RedisBackend instance
function RedisBackend.new()
    local self = setmetatable({}, RedisBackend)
    return self
end

--- Get a Redis client connection
-- @return redis client or nil
function RedisBackend:get_client()
    local red = redis:new()
    red:set_timeout(TIMEOUT)
    
    local ok, err = red:connect(HOST, PORT)
    if not ok then
        ngx.log(ngx.ERR, "Failed to connect to Redis: ", err)
        return nil
    end
    
    if PASSWORD then
        local res, err = red:auth(PASSWORD)
        if not res then
            ngx.log(ngx.ERR, "Failed to authenticate with Redis: ", err)
            return nil
        end
    end
    
    return red
end

--- Release Redis connection back to pool
-- @param red Redis client
function RedisBackend:release_client(red)
    if red then
        -- Put connection back into pool (10s idle, 100 connections max)
        local ok, err = red:set_keepalive(10000, 100)
        if not ok then
            ngx.log(ngx.DEBUG, "Failed to set Redis keepalive: ", err)
        end
    end
end

--- Convert Redis hash array to Lua table
-- @param array_value Array from HGETALL
-- @return table
local function hgetall_to_table(array_value)
    local result = {}
    local next_key
    
    for i, v in ipairs(array_value) do
        if i % 2 == 1 then
            next_key = v
        else
            result[next_key] = v
        end
    end
    
    return result
end

local function is_valid_target(value)
    return value ~= nil and value ~= ngx.null and value ~= ""
end

--- Build Redis key for a record
-- @param kind Record kind
-- @param key Record key
-- @return Redis key string
function RedisBackend:build_key(kind, key)
    -- Map kind to Redis key pattern for backward compatibility
    if kind == "route" then
        return PREFIX .. ":routes:" .. key
    elseif kind == "certificate" then
        return PREFIX .. ":certificates:" .. key
    else
        return PREFIX .. ":" .. kind .. ":" .. key
    end
end

--- Build Redis key for settings (legacy pattern)
-- @param key Record key
-- @return Redis key string
function RedisBackend:build_settings_key(key)
    return PREFIX .. ":settings:" .. key
end

--- Initialize backend (no-op for Redis, tables created on demand)
-- @return boolean
function RedisBackend:init()
    -- Test connection
    local red = self:get_client()
    if not red then
        return false
    end
    
    local ok, err = red:ping()
    self:release_client(red)
    
    if not ok then
        ngx.log(ngx.ERR, "Redis ping failed: ", err)
        return false
    end
    
    ngx.log(ngx.INFO, "Redis backend initialized: ", HOST, ":", PORT)
    return true
end

--- Get a record by kind and key
-- @param kind The record kind
-- @param key The record key
-- @return value, meta_table or nil
function RedisBackend:get(kind, key)
    local red = self:get_client()
    if not red then
        return nil, nil
    end
    
    local redis_key = self:build_key(kind, key)
    
    -- For routes, check both new format and legacy format
    if kind == "route" then
        local settings_key = self:build_settings_key(key)
        local settings_array = red:hgetall(settings_key)
        
        local meta = {}
        if settings_array and type(settings_array) == "table" and #settings_array > 0 then
            meta = hgetall_to_table(settings_array)
            -- Convert string booleans
            if meta.enforce_https then
                meta.enforce_https = meta.enforce_https == "true" or meta.enforce_https == "1"
            end
        end

        local value = nil

        if key == wildcard_source then
            value = red:get(redis_key)
        elseif is_valid_target(meta.target) then
            value = meta.target
        else
            value = red:get(redis_key)
        end

        if not is_valid_target(value) then
            self:release_client(red)
            return nil, nil
        end
        
        self:release_client(red)
        return value, meta
    else
        -- For other kinds (certificates), use HASH with value and meta fields
        local data = red:hgetall(redis_key)
        
        if not data or data == ngx.null or #data == 0 then
            self:release_client(red)
            return nil, nil
        end
        
        local hash = hgetall_to_table(data)
        self:release_client(red)
        
        local meta = {}
        if hash.meta then
            local ok, decoded = pcall(cjson.decode, hash.meta)
            if ok then
                meta = decoded
            end
        end
        
        return hash.value, meta
    end
end

--- Set a record (insert or update)
-- @param kind The record kind
-- @param key The record key
-- @param value The record value
-- @param meta Table of metadata
-- @return boolean success
function RedisBackend:set(kind, key, value, meta)
    local red = self:get_client()
    if not red then
        return false
    end
    
    local redis_key = self:build_key(kind, key)
    
    -- For routes, maintain backward compatibility
    if kind == "route" then
        local settings_key = self:build_settings_key(key)

        if key == wildcard_source then
            local ok, err = red:set(redis_key, value)
            if not ok then
                ngx.log(ngx.ERR, "Failed to set route: ", err)
                self:release_client(red)
                return false
            end
        else
            red:del(redis_key)
        end

        red:del(settings_key)

        if meta and next(meta) then
            local args = {}
            for k, v in pairs(meta) do
                table.insert(args, k)
                if type(v) == "boolean" then
                    table.insert(args, v and "true" or "false")
                else
                    table.insert(args, tostring(v))
                end
            end

            if #args > 0 then
                local ok, err = red:hmset(settings_key, unpack(args))
                if not ok then
                    ngx.log(ngx.ERR, "Failed to set route settings: ", err)
                    self:release_client(red)
                    return false
                end
            end
        end
        
        self:release_client(red)
        return true
    else
        -- For other kinds, use HASH with value and meta fields
        local meta_json = "{}"
        if meta and next(meta) then
            local ok, encoded = pcall(cjson.encode, meta)
            if ok then
                meta_json = encoded
            end
        end
        
        local ok, err = red:hmset(redis_key, "value", value, "meta", meta_json)
        self:release_client(red)
        
        if not ok then
            ngx.log(ngx.ERR, "Failed to set record: ", err)
            return false
        end
        
        return true
    end
end

--- Delete a record
-- @param kind The record kind
-- @param key The record key
-- @return boolean success
function RedisBackend:delete(kind, key)
    local red = self:get_client()
    if not red then
        return false
    end
    
    local redis_key = self:build_key(kind, key)
    red:del(redis_key)
    
    -- For routes, also delete legacy settings key
    if kind == "route" then
        local settings_key = self:build_settings_key(key)
        red:del(settings_key)
    end
    
    self:release_client(red)
    return true
end

--- List all records of a specific kind
-- @param kind The record kind
-- @return array of {key, value, meta}
function RedisBackend:list(kind)
    local red = self:get_client()
    if not red then
        return {}
    end
    
    local pattern
    if kind == "route" then
        pattern = nil
    elseif kind == "certificate" then
        pattern = PREFIX .. ":certificates:*"
    else
        pattern = PREFIX .. ":" .. kind .. ":*"
    end
    
    local results = {}
    local prefix_len
    
    if kind == "route" then
        local route_keys = red:keys(PREFIX .. ":routes:*") or {}
        local settings_keys = red:keys(PREFIX .. ":settings:*") or {}
        local seen = {}
        local hosts = {}

        prefix_len = #(PREFIX .. ":routes:")
        for _, redis_key in ipairs(route_keys) do
            local record_key = redis_key:sub(prefix_len + 1)
            if not seen[record_key] then
                seen[record_key] = true
                table.insert(hosts, record_key)
            end
        end

        prefix_len = #(PREFIX .. ":settings:")
        for _, redis_key in ipairs(settings_keys) do
            local record_key = redis_key:sub(prefix_len + 1)
            if not seen[record_key] then
                seen[record_key] = true
                table.insert(hosts, record_key)
            end
        end

        self:release_client(red)

        for _, record_key in ipairs(hosts) do
            local value, meta = self:get(kind, record_key)

            if value then
                table.insert(results, {
                    key = record_key,
                    value = value,
                    meta = meta or {}
                })
            end
        end

        return results
    elseif kind == "certificate" then
        prefix_len = #(PREFIX .. ":certificates:")
    else
        prefix_len = #(PREFIX .. ":" .. kind .. ":")
    end

    local keys, err = red:keys(pattern)
    if not keys or keys == ngx.null then
        self:release_client(red)
        return {}
    end
    
    for _, redis_key in ipairs(keys) do
        local record_key = redis_key:sub(prefix_len + 1)
        local value, meta = self:get(kind, record_key)
        
        if value then
            table.insert(results, {
                key = record_key,
                value = value,
                meta = meta or {}
            })
        end
    end
    
    self:release_client(red)
    return results
end

--- Check if a record exists
-- @param kind The record kind
-- @param key The record key
-- @return boolean
function RedisBackend:exists(kind, key)
    local red = self:get_client()
    if not red then
        return false
    end
    
    local exists = 0

    if kind == "route" then
        if key == wildcard_source then
            local redis_key = self:build_key(kind, key)
            exists = red:exists(redis_key)
        else
            local settings_key = self:build_settings_key(key)
            local target = red:hget(settings_key, "target")
            if is_valid_target(target) then
                exists = 1
            else
                local redis_key = self:build_key(kind, key)
                exists = red:exists(redis_key)
            end
        end
    else
        local redis_key = self:build_key(kind, key)
        exists = red:exists(redis_key)
    end
    
    self:release_client(red)
    return exists == 1
end

--- Get record with fallback to another key
-- @param kind The record kind
-- @param key The primary key
-- @param fallback_key The fallback key if primary not found
-- @return value, meta_table or nil
function RedisBackend:get_with_fallback(kind, key, fallback_key)
    local value, meta = self:get(kind, key)
    if value then
        return value, meta
    end
    
    return self:get(kind, fallback_key)
end

--- Close connections (no-op, connections are pooled)
function RedisBackend:close()
    -- Connections are managed via keepalive pool
end

--- Get backend statistics
-- @return table with stats
function RedisBackend:stats()
    local red = self:get_client()
    if not red then
        return {error = "Connection failed"}
    end
    
    local info = red:info()
    self:release_client(red)
    
    return {
        host = HOST,
        port = PORT,
        prefix = PREFIX,
        connected = info ~= nil
    }
end

-- Export configuration for backward compatibility
RedisBackend.prefix = PREFIX
RedisBackend.host = HOST
RedisBackend.port = PORT

return RedisBackend

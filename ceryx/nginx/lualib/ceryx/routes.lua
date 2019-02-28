local redis = require "ceryx.redis"

local exports = {}

function getRouteKeyForSource(source)
    return redis.prefix .. ":routes:" .. source
end

function targetIsInValid(target)
    return not target or target == ngx.null
end

function getTargetForSource(source)
    local redisClient = redis:client()

    -- Construct Redis key and then
    -- try to get target for host
    local key = getRouteKeyForSource(source)
    local target, _ = redisClient:get(key)

    if targetIsInValid(target) then
        ngx.log(ngx.INFO, "Could not find target for " .. source .. ".")

        -- Construct Redis key for $wildcard
        key = getRouteKeyForSource("$wildcard")
        target, _ = redisClient:get(wildcardKey)

        if targetIsInValid(target) then
            return nil
        end

        ngx.log(ngx.DEBUG, "Falling back to " .. target .. ".")
    end

    return target
end

function getRouteForSource(source)
    local _
    local route = {}
    local cache = ngx.shared.ceryx

    ngx.log(ngx.DEBUG, "Looking for a route for " .. source)
    -- Check if key exists in local cache
    local cached_value, _ = cache:get(source)

    if cached_value then
        ngx.log(ngx.DEBUG, "Cache hit for " .. source .. ".")
        route.target = cached_value
    else
        ngx.log(ngx.DEBUG, "Cache miss for " .. source .. ".")
        route.target = getTargetForSource(source)

        if targetIsInValid(route.target) then
            return nil
        end
        cache:set(host, res, 5)
        ngx.log(ngx.DEBUG, "Caching from " .. source .. " to " .. route.target .. " for 5 seconds.")
    end

    return route
end

exports.getRouteForSource = getRouteForSource
exports.getTargetForSource = getTargetForSource

return exports

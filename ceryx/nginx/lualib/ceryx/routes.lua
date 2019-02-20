local redis = require "ceryx.redis"
local prefix = redis.prefix()

local exports


function getRouteForSource(source)
    local _
    local target
    local settings = {}
    local cache = ngx.shared.ceryx

    ngx.log(ngx.DEBUG, "Looking for a route for " .. source)
    -- Check if key exists in local cache
    local cached_value, _ = cache:get(host)

    if cached_value then
    ngx.log(ngx.DEBUG, "Cache hit for " .. source .. ".")
        target = cached_value
    else
        ngx.log(ngx.DEBUG, "Cache miss for " .. host .. ".")

        -- Construct Redis key
        local key = prefix .. ":routes:" .. host
        
        -- Try to get target for host
        res, err = redisClient:get(key)
        if not res or res == ngx.null then
            ngx.log(ngx.INFO, "Could not find target for " .. host .. ".")

            -- Construct Redis key for $wildcard
            key = prefix .. ":routes:$wildcard"
            res, err = redisClient:get(key)
            if not res or res == ngx.null then
                ngx.log(ngx.INFO, "No $wildcard target configured for fallback. Exiting with Bad Gateway.")
                return ngx.exit(ngx.HTTP_SERVICE_UNAVAILABLE)
            else
                ngx.log(ngx.DEBUG, "Falling back to " .. res .. ".")
            end
        end
    end

    return route
end


return exports
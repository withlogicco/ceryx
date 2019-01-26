local host = ngx.var.host
local is_not_https = (ngx.var.scheme ~= "https")
local cache = ngx.shared.ceryx

function route(source, target)
    ngx.var.container_url = target
    ngx.log(ngx.INFO, "Routing request for " .. source .. " to " .. target .. ".")
end

local prefix = os.getenv("CERYX_REDIS_PREFIX")
if not prefix then prefix = "ceryx" end

-- Prepare the Redis client
ngx.log(ngx.DEBUG, "Preparing Redis client.")
local redis = require "resty.redis"
local red = redis:new()
red:set_timeout(100) -- 100 ms
local redis_host = os.getenv("CERYX_REDIS_HOST")
if not redis_host then redis_host = "127.0.0.1" end
local redis_port = os.getenv("CERYX_REDIS_PORT")
if not redis_port then redis_port = 6379 end
local redis_password = os.getenv("CERYX_REDIS_PASSWORD")
if not redis_password then redis_password = nil end
local res, err = red:connect(redis_host, redis_port)

-- Return if could not connect to Redis
if not res then
    ngx.log(ngx.DEBUG, "Could not prepare Redis client: " .. err)
    return ngx.exit(ngx.HTTP_SERVER_ERROR)
end

ngx.log(ngx.DEBUG, "Redis client prepared.")

if redis_password then
    ngx.log(ngx.DEBUG, "Authenticating with Redis.")
    local res, err = red:auth(redis_password)
    if not res then
        ngx.ERR("Could not authenticate with Redis: ", err)
        return ngx.exit(ngx.HTTP_SERVER_ERROR)
    end
end
ngx.log(ngx.DEBUG, "Authenticated with Redis.")

if is_not_https then
    local settings_key = prefix .. ":settings:" .. host
    local enforce_https, flags = cache:get(host .. ":enforce_https")

    if enforce_https == nil then
        local res, flags = red:hget(settings_key, "enforce_https")
        enforce_https = tonumber(res)
        cache:set(host .. ":enforce_https", enforce_https, 5)
    end

    if enforce_https == 1 then
        return ngx.redirect("https://" .. host .. ngx.var.request_uri, ngx.HTTP_MOVED_PERMANENTLY)
    end
end

-- Check if key exists in local cache
res, flags = cache:get(host)
if res then
    ngx.log(ngx.DEBUG, "Cache hit for " .. host .. ".")
    route(host, res)
else
    ngx.log(ngx.DEBUG, "Cache miss for " .. host .. ".")

    -- Construct Redis key
    local key = prefix .. ":routes:" .. host
    
    -- Try to get target for host
    res, err = red:get(key)
    if not res or res == ngx.null then
        ngx.log(ngx.INFO, "Could not find target for " .. host .. ".")

        -- Construct Redis key for $wildcard
        key = prefix .. ":routes:$wildcard"
        res, err = red:get(key)
        if not res or res == ngx.null then
            ngx.log(ngx.INFO, "No $wildcard target configured for fallback. Exiting with Bad Gateway.")
            return ngx.exit(ngx.HTTP_SERVICE_UNAVAILABLE)
        else
            ngx.log(ngx.DEBUG, "Falling back to " .. res .. ".")
        end
    end
end

-- Save found key to local cache for 5 seconds
route(host, res)
cache:set(host, res, 5)
ngx.log(ngx.DEBUG, "Saving route from " .. host .. " to " .. res .. " in local cache for 5 seconds.")

local host = ngx.var.host
local is_not_https = (ngx.var.scheme ~= "https")
local cache = ngx.shared.ceryx

local get_redis_client = require "redis_client"
local red = get_redis_client()

local prefix = os.getenv("CERYX_REDIS_PREFIX")
if not prefix then prefix = "ceryx" end


if is_not_https then
    local settings_key = prefix .. ":settings:" .. host
    local enforce_https, flags = cache:get(host .. ":enforce_https")

    if enforce_https == nil then
        local res, flags = red:hget(settings_key, "enforce_https")
        enforce_https = tonumber(res)
        cache:set(host .. ":enforce_https", enforce_https, 5)
    end

    if enforce_https then
        return ngx.redirect("https://" .. host .. ngx.var.request_uri, ngx.HTTP_MOVED_PERMANENTLY)
    end
end

-- Check if key exists in local cache
res, flags = cache:get(host)
if res then
    ngx.var.container_url = res
    return
end

-- Construct Redis key
local key = prefix .. ":routes:" .. host

-- Try to get target for host
res, err = red:get(key)
if not res or res == ngx.null then
    -- Construct Redis key for $wildcard
    key = prefix .. ":routes:$wildcard"
    res, err = red:get(key)
    if not res or res == ngx.null then
        return ngx.exit(ngx.HTTP_BAD_GATEWAY)
    end
    ngx.var.container_url = res
    return
end

-- Save found key to local cache for 5 seconds
cache:set(host, res, 5)

ngx.var.container_url = res

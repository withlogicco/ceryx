local container_url = ngx.var.container_url
local host = ngx.var.host

-- Check if key exists in local cache
local cache = ngx.shared.ceryx
local res, flags = cache:get(host)
if res then
    ngx.var.container_url = res
    return
end

local redis = require "resty.redis"
local red = redis:new()
red:set_timeout(100) -- 100 ms
local redis_host = os.getenv("CERYX_REDIS_HOST")
if not redis_host then redis_host = "127.0.0.1" end
local redis_port = os.getenv("CERYX_REDIS_PORT")
if not redis_port then redis_port = 6379 end
local res, err = red:connect(redis_host, redis_port)

-- Exit if could not connect to Redis
if not res then
    ngx.log(ngx.ERR, "failed to connect to redis: " .. err)
    ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
end

-- Construct Redis key
local prefix = os.getenv("CERYX_REDIS_PREFIX")
if not prefix then prefix = "ceryx" end
local key = prefix .. ":routes:" .. host

-- Try to get target for host
res, err = red:get(key)

-- Exit if route could not be read
if err then
    ngx.log(ngx.ERR, "error reading route: " .. err)
    ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
end

if not res or res == ngx.null then
    ngx.log(ngx.WARN, "no route for host " .. host)

    -- Construct Redis key for $wildcard
    key = prefix .. ":routes:$wildcard"
    res, err = red:get(key)
    if not res or res == ngx.null then
        ngx.exit(ngx.HTTP_NOT_FOUND)
    end
    ngx.var.container_url = res
    return
end

-- Save found key to local cache for 5 seconds
cache:set(host, res, 5)

ngx.var.container_url = res

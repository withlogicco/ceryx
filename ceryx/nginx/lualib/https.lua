auto_ssl = (require "resty.auto-ssl").new()

-- Define a function to determine which SNI domains to automatically handle
-- and register new certificates for. Defaults to not allowing any domains,
-- so this must be configured.
auto_ssl:set("allow_domain", function(domain)
    local host = domain

    -- Check if key exists in local cache
    local cache = ngx.shared.ceryx
    local res, flags = cache:get(host)
    if res then
        return true
    end

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
        ngx.log(ngx.ERR, "Error connecting to redis: " .. (err or ""))
        return false
    end

    -- Authenticate with Redis if necessary
    if redis_password then
        local res, err = red:auth(redis_password)
        if not res then
            ngx.log(ngx.ERR, "Failed to authenticate with redis: ", err)
            return false
        end
    end

    -- Construct Redis key
    local prefix = os.getenv("CERYX_REDIS_PREFIX")
    if not prefix then prefix = "ceryx" end
    local key = prefix .. ":routes:" .. host

    -- Try to get target for host
    res, err = red:get(key)
    if not res or res == ngx.null then
        return false
    end

    -- Save found key to local cache for 5 seconds
    cache:set(host, res, 5)

    return true
end)

-- Set the resty-auto-ssl storage to Redis, using the CERYX_* env variables
local redis_host = os.getenv("CERYX_REDIS_HOST")
if not redis_host then redis_host = "127.0.0.1" end
local redis_port = os.getenv("CERYX_REDIS_PORT")
if not redis_port then redis_port = 6379 end
auto_ssl:set("storage_adapter", "resty.auto-ssl.storage_adapters.redis")
auto_ssl:set("redis", {
    host = redis_host,
    port = redis_port
})

auto_ssl:init()
require "resty.core"
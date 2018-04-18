-- Prepare the Redis client
local redis = require "resty.redis"
local redis_host = os.getenv("CERYX_REDIS_HOST")
if not redis_host then redis_host = "127.0.0.1" end
local redis_port = os.getenv("CERYX_REDIS_PORT")
if not redis_port then redis_port = 6379 end
local redis_password = os.getenv("CERYX_REDIS_PASSWORD")
if not redis_password then redis_password = nil end

function get_redis_client()
    local red = redis:new()
    red:set_timeout(100) -- 100 ms
    local res, err = red:connect(redis_host, redis_port)

    -- Return if could not connect to Redis
    if not res then
        return ngx.exit(ngx.HTTP_BAD_GATEWAY)
    end

    if redis_password then
        local res, err = red:auth(redis_password)
        if not res then
        ngx.ERR("Failed to authenticate Redis: ", err)
        return
        end
    end

    return red
end

return get_redis_client

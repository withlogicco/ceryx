local redis = require "resty.redis"

local exports = {}

function exports.prefix()
    local prefix = os.getenv("CERYX_REDIS_PREFIX")
    if not prefix then prefix = "ceryx" end
    return prefix
end

function exports.client()
    local prefix = exports.prefix()

    -- Prepare the Redis client
    ngx.log(ngx.DEBUG, "Preparing Redis client.")
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

    return red
end

return exports
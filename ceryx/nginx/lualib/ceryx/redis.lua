--local redis = require "resty.redis"
local rcluster = require "resty.rcluster"
local utils = require "ceryx.utils"

local prefix = utils.getenv("CERYX_REDIS_PREFIX", "ceryx")
local host = utils.getenv("CERYX_REDIS_HOST", "127.0.0.1")
local port = utils.getenv("CERYX_REDIS_PORT", 6379)
local password = utils.getenv("CERYX_REDIS_PASSWORD", nil)
local timeout = utils.getenv("CERYX_REDIS_TIMEOUT", 100)  -- 100 ms

local exports = {}

function exports.client()
    -- Prepare the Redis client
    ngx.log(ngx.DEBUG, "Preparing Redis client.")

    --local red = redis:new()
    --[[local server = {
        { host = host, port = port}
    }]]--

    local server = {}
    --table.insert(server, { host = host, port = port})
    --ngx.log(ngx.DEBUG, "Server = " .. server)

    local red = rcluster:new({
        timeout = timeout,
        server =  {
            {
                ["host"] = host, ["port"] = port
            },
        }
    })
    --red:set_timeout(timeout) 

    local res, err = red:connect(host, port)

    -- Return if could not connect to Redis
    if not res then
        ngx.log(ngx.DEBUG, "Could not prepare Redis client: " .. err)
        return ngx.exit(ngx.HTTP_SERVER_ERROR)
    end

    ngx.log(ngx.DEBUG, "Redis client prepared.")

    --[[if password then
        ngx.log(ngx.DEBUG, "Authenticating with Redis.")
        local res, err = red:auth(password)
        if not res then
            ngx.ERR("Could not authenticate with Redis: ", err)
            return ngx.exit(ngx.HTTP_SERVER_ERROR)
        end
    end
    ngx.log(ngx.DEBUG, "Authenticated with Redis.")]]--

    return red
end

exports.prefix = prefix
exports.host = host
exports.port = port
exports.password = password

return exports

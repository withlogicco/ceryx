auto_ssl = (require "resty.auto-ssl").new()

local redis = require "ceryx.redis"
local routes = require "ceryx.routes"

-- Define a function to determine which SNI domains to automatically handle
-- and register new certificates for. Defaults to not allowing any domains,
-- so this must be configured.
auto_ssl:set(
    "allow_domain",
    function(domain)
        local redisClient = redis:client()
        local host = domain
        local target = routes.getTargetForSource(host, redisClient)

        if target == nil then
            return target
        end

        return true
    end
)

-- Set the resty-auto-ssl storage to Redis, using the CERYX_* env variables
auto_ssl:set("storage_adapter", "resty.auto-ssl.storage_adapters.redis")
auto_ssl:set(
    "redis",
    {
        host = redis.host,
        port = redis.port
    }
)

auto_ssl:init()
require "resty.core"

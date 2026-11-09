auto_ssl = (require "resty.auto-ssl").new()

local redis = require "ceryx.redis"
local routes = require "ceryx.routes"
local utils = require "ceryx.utils"

local storage_backend = utils.getenv("CERYX_STORAGE_BACKEND", "redis")
local lets_encrypt_ca = utils.getenv("CERYX_LETS_ENCRYPT_CA", "")

-- Define a function to determine which SNI domains to automatically handle
-- and register new certificates for. Defaults to not allowing any domains,
-- so this must be configured.
auto_ssl:set(
    "allow_domain",
    function(domain)
        local redisClient = nil
        if storage_backend == "redis" then
            redisClient = redis:client()
        end

        local host = domain
        local target = routes.getTargetForSource(host, redisClient)

        if target == nil then
            return target
        end

        return true
    end
)

if lets_encrypt_ca ~= "" then
    auto_ssl:set("ca", lets_encrypt_ca)
end

if storage_backend == "sqlite" then
    auto_ssl:set("storage_adapter", "ceryx.backends.sqlite_certs")
else
    -- Set the resty-auto-ssl storage to Redis, using the CERYX_* env variables
    auto_ssl:set("storage_adapter", "resty.auto-ssl.storage_adapters.redis")
    auto_ssl:set(
        "redis",
        {
            host = redis.host,
            port = redis.port,
            auth = redis.password
        }
    )
end

auto_ssl:init()
require "resty.core"

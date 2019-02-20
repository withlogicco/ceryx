local redis = require "ceryx.redis"
local utils = require "ceryx.utils"

local redisClient = redis:client()
local prefix = redis.prefix()

local host = ngx.var.host
local cache = ngx.shared.ceryx

local is_not_https = (ngx.var.scheme ~= "https")
local settings_key = prefix .. ":settings:" .. host


function route(source, target, mode)
    ngx.log(ngx.DEBUG, "Received " .. mode ..  " routing request from " .. source .. " to " .. target)

    target = utils.ensure_protocol(target)
    target = utils.ensure_no_trailing_slash(target)

    local full_target = target .. ngx.var.request_uri

    if mode == "redirect" then
        ngx.log(ngx.INFO, "Redirecting request for " .. source .. " to " .. full_target .. ".")
        return ngx.redirect(full_target, ngx.HTTP_MOVED_PERMANENTLY)
    end

    ngx.var.target = full_target
    ngx.log(ngx.INFO, "Proxying request for " .. source .. " to " .. full_target .. ".")
end

if is_not_https then
    local enforce_https, flags = cache:get(host .. ":enforce_https")

    if enforce_https == nil then
        local res, flags = redisClient:hget(settings_key, "enforce_https")
        enforce_https = tonumber(res)
        cache:set(host .. ":enforce_https", enforce_https, 5)
    end

    if enforce_https == 1 then
        return ngx.redirect("https://" .. host .. ngx.var.request_uri, ngx.HTTP_MOVED_PERMANENTLY)
    end
end

-- Get routing mode
local mode, mode_flags = redisClient:hget(settings_key, "mode")

-- Check if key exists in local cache
res, flags = cache:get(host)
if res then
    ngx.log(ngx.DEBUG, "Cache hit for " .. host .. ".")
    route(host, res, mode)
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

-- Save found key to local cache for 5 seconds
route(host, res, mode)
cache:set(host, res, 5)
ngx.log(ngx.DEBUG, "Saving route from " .. host .. " to " .. res .. " in local cache for 5 seconds.")

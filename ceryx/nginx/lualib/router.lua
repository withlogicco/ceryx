local redis = require "ceryx.redis"
local routes = require "ceryx.routes"
local utils = require "ceryx.utils"

local redisClient = redis:client()

local host = ngx.var.host
local cache = ngx.shared.ceryx

local is_not_https = (ngx.var.scheme ~= "https")
local settings_key = redis.prefix .. ":settings:" .. host

function formatTarget(target)
    target = utils.ensure_protocol(target)
    target = utils.ensure_no_trailing_slash(target)

    return target .. ngx.var.request_uri
end

function redirect(source, target)
    ngx.log(ngx.INFO, "Redirecting request for " .. source .. " to " .. target .. ".")
    return ngx.redirect(target, ngx.HTTP_MOVED_PERMANENTLY)
end

function proxy(source, target)
    ngx.var.target = target
    ngx.log(ngx.INFO, "Proxying request for " .. source .. " to " .. target .. ".")
end

function routeRequest(source, target, mode)
    ngx.log(ngx.DEBUG, "Received " .. mode .. " routing request from " .. source .. " to " .. target)

    target = formatTarget(target)

    if mode == "redirect" then
        return redirect(source, target)
    end

    return proxy(source, target)
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

-- Get routing mode (default to "proxy")
local mode, mode_flags = redisClient:hget(settings_key, "mode")
mode = mode or "proxy"

ngx.log(ngx.INFO, "HOST " .. host)
local route = routes.getRouteForSource(host)

if route == nil then
    ngx.log(ngx.INFO, "No $wildcard target configured for fallback. Exiting with Bad Gateway.")
    return ngx.exit(ngx.HTTP_SERVICE_UNAVAILABLE)
end

-- Save found key to local cache for 5 seconds
routeRequest(host, route.target, mode)

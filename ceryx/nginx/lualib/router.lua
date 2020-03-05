local redis = require "ceryx.redis"
local routes = require "ceryx.routes"
local utils = require "ceryx.utils"

local redisClient = redis:client()

local host = ngx.var.host
local request_uri = ngx.var.request_uri:sub(2)
local cache = ngx.shared.ceryx

local is_not_https = (ngx.var.scheme ~= "https")

function formatTargetHostSource(target)
    target = utils.ensure_protocol(target)
    target = utils.ensure_no_trailing_slash(target)
    return target .. ngx.var.request_uri
end

function formatTargetRequestUriSource(target)
    target = utils.ensure_protocol(target)
    return target
end

function redirect(source, target, headers)
    ngx.log(ngx.INFO, "Redirecting request for " .. source)
    for k,v in pairs(headers) do
        ngx.headers[k] = v
    end
    return ngx.redirect(target, ngx.HTTP_MOVED_PERMANENTLY)
end

function proxy(source, target, headers)
    ngx.var.target = target
    for k,v in pairs(headers) do
        ngx.req.set_header(k, v)
end
    ngx.log(ngx.INFO, "Proxying request for " .. source)
end

function routeRequest(source, target, mode, headers)
    ngx.log(ngx.DEBUG, "Received " .. mode .. " routing request from " .. source .. " to " .. target)

    if mode == "redirect" then
        return redirect(source, target, headers)
    end

    return proxy(source, target, headers)
end

if is_not_https then
    local settings_key = routes.getSettingsKeyForSource(host)
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

ngx.log(ngx.INFO, "Try host route for " .. host)
local route = routes.getRouteForSource(host)

if route ~= nil then
    return routeRequest(host, formatTargetHostSource(route.target), route.mode, route.headers)
end

ngx.log(ngx.INFO, "Try request_uri route for " .. request_uri)
route = routes.getRouteForSource(request_uri)

if route ~= nil then
    return routeRequest(request_uri, formatTargetRequestUriSource(route.target), route.mode, route.headers)
end

ngx.log(ngx.INFO, "No $wildcard target configured for fallback. Exiting with Bad Gateway.")
ngx.exit(ngx.HTTP_SERVICE_UNAVAILABLE)

local routes = require "ceryx.routes"
local settings = require "ceryx.settings"
local utils = require "ceryx.utils"
local mtls = require "mtls"

local host = ngx.var.host
local cache = ngx.shared.ceryx

local is_not_https = (ngx.var.scheme ~= "https")

mtls.enforce(host)

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
    local enforce_https = settings.getSettingForHost(host, "enforce_https", true)

    if enforce_https == true or enforce_https == 1 or enforce_https == "true" or enforce_https == "1" then
        return ngx.redirect("https://" .. host .. ngx.var.request_uri, ngx.HTTP_MOVED_PERMANENTLY)
    end
end

ngx.log(ngx.INFO, "HOST " .. host)
local route = routes.getRouteForSource(host)

if route == nil then
    ngx.log(ngx.INFO, "No $wildcard target configured for fallback. Exiting with Bad Gateway.")
    return ngx.exit(ngx.HTTP_SERVICE_UNAVAILABLE)
end

-- Save found key to local cache for 5 seconds
routeRequest(host, route.target, route.mode)

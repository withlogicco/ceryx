--[[
    Ceryx API entry point (content phase)

    Maps each API path to its handlers by method. Methods a path does not
    list get 405 with an Allow header built from the same table, so the
    supported methods are declared once (and in docs/openapi.yaml).
]]

local api = require "ceryx.api"

local ROUTES = {
    {"^/api/routes/?$", {GET = api.list_routes, POST = api.create_route}},
    {"^/api/routes/([^/]+)/?$", {GET = api.get_route, PUT = api.update_route, DELETE = api.delete_route}},
    {"^/api/certificates/?$", {GET = api.list_certificates, POST = api.create_certificate}},
    {"^/api/certificates/([^/]+)/?$", {GET = api.get_certificate, PUT = api.update_certificate, DELETE = api.delete_certificate}},
}

local METHOD_ORDER = {"GET", "POST", "PUT", "DELETE"}

local function allowed_methods(handlers)
    local allowed = {}
    for _, method in ipairs(METHOD_ORDER) do
        if handlers[method] then
            table.insert(allowed, method)
        end
    end
    return table.concat(allowed, ", ")
end

-- Match the decoded, normalised URI, as NGINX locations do.
local uri = ngx.var.uri

for _, route in ipairs(ROUTES) do
    local match = ngx.re.match(uri, route[1], "jo")
    if match then
        local handler = route[2][ngx.req.get_method()]
        if handler then
            return handler(match[1])
        end
        return api.method_not_allowed(allowed_methods(route[2]))
    end
end

api.handle_default()

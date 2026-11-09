--[[
    Ceryx API Module
    
    HTTP API handlers for managing routes and certificates.
    Uses the storage abstraction layer for backend-agnostic operations.
]]

local cjson = require "cjson"
local routes = require "ceryx.routes"
local certificates = require "ceryx.certificates"
local mtls = require "ceryx.mtls"

if cjson.encode_escape_forward_slash then
    cjson.encode_escape_forward_slash(false)
end

-- Route handlers
local exports = {}

local function encode_array(value)
    if not value or #value == 0 then
        return "[]"
    end

    return cjson.encode(value)
end

local function is_set(value)
    return value ~= nil and value ~= ngx.null
end

local function respond_error(status, detail)
    ngx.status = status
    ngx.say(cjson.encode({detail = detail}))
end

local function bad_request(detail)
    respond_error(400, detail)
end

-- Read and decode the JSON request body. Responds with 400 and returns nil
-- when the body is missing or is not valid JSON.
local function read_json_body()
    ngx.req.read_body()
    local body_data = ngx.req.get_body_data()

    if not body_data then
        bad_request("Request body is required")
        return nil
    end

    local ok, data = pcall(cjson.decode, body_data)
    if not ok then
        bad_request("Invalid JSON in request body")
        return nil
    end

    return data
end

function exports.handle_default()
    local uri = ngx.var.uri
    ngx.status = 404
    ngx.say(cjson.encode({detail = "Invalid route: " .. uri}))
end

function exports.method_not_allowed(allowed)
    if allowed then
        ngx.header["Allow"] = allowed
    end
    ngx.status = 405
    ngx.say(cjson.encode({detail = "Method not allowed"}))
end

function exports.list_routes()
    local routeList = routes.listRoutes()
    
    if not routeList then
        routeList = {}
    end

    ngx.say(encode_array(routeList))
end

function exports.get_route(host)
    local route = routes.fetchAndSerializeRoute(host)

    if not route then
        local err = { detail = "No route found for " .. host }
        ngx.status = 404
        ngx.say(cjson.encode(err))
        return
    end

    ngx.say(cjson.encode(route))
end

function exports.create_route()
    local data = read_json_body()
    if not data then
        return
    end

    local required_fields = { "source", "target" }
    
    for _, field in ipairs(required_fields) do
        if not data[field] then
            local err = { detail = "The '" .. field .. "' field is required." }
            ngx.status = 400
            ngx.say(cjson.encode(err))
            return
        end
    end

    local with_defaults, defaults_error = routes.withCreationDefaults(data.settings)
    if not with_defaults then
        respond_error(500, defaults_error)
        return
    end

    local settings = routes.constructSettings(with_defaults)
    local valid, invalid, status = mtls.validate(settings)
    if not valid then
        respond_error(status, invalid)
        return
    end

    local success = routes.setRoute(data.source, data.target, settings)

    if not success then
        ngx.log(ngx.ERR, "Failed to create route for " .. data.source)
        local err = { detail = "Failed to create route" }
        ngx.status = 500
        ngx.say(cjson.encode(err))
        return
    end

    local route = routes.fetchAndSerializeRoute(data.source)

    ngx.status = 201
    ngx.say(cjson.encode(route))
end

function exports.update_route(host)
    local route = routes.fetchAndSerializeRoute(host)

    if not route then
        local err = { detail = "No route found for " .. host }
        ngx.status = 404
        ngx.say(cjson.encode(err))
        return
    end

    local data = read_json_body()
    if not data then
        return
    end

    if is_set(data.source) and data.source ~= host then
        bad_request("The 'source' field must match the route in the URL.")
        return
    end

    -- Merge new data with existing route
    local new_target = data.target
    if not new_target or new_target == ngx.null then
        new_target = route.target
    end

    local settings = routes.constructSettings(data.settings, route.settings)
    local valid, invalid, status = mtls.validate(settings)
    if not valid then
        respond_error(status, invalid)
        return
    end

    local success = routes.setRoute(host, new_target, settings)

    if not success then
        ngx.log(ngx.ERR, "Failed to update route for " .. host)
        local err = { detail = "Failed to update route" }
        ngx.status = 500
        ngx.say(cjson.encode(err))
        return
    end

    route = routes.fetchAndSerializeRoute(host)
    ngx.say(cjson.encode(route))
end

function exports.delete_route(host)
    local success = routes.deleteRoute(host)

    if success then
        ngx.status = 204
        return
    end

    ngx.status = 500
    ngx.say(cjson.encode({detail = "Failed to delete route"}))
end

-- Certificate endpoints
function exports.list_certificates()
    local certList = certificates.listCertificates()
    
    if not certList then
        certList = {}
    end
    
    -- Format for API response
    local result = {}
    for _, cert in ipairs(certList) do
        table.insert(result, {
            domain = cert.key,
            meta = cert.meta
        })
    end

    ngx.say(encode_array(result))
end

function exports.get_certificate(domain)
    local data = certificates.getCertificatesForHost(domain)

    if not data then
        local err = { detail = "No certificate found for " .. domain }
        ngx.status = 404
        ngx.say(cjson.encode(err))
        return
    end

    -- Return certificate info (without private key for security)
    ngx.say(cjson.encode({
        domain = domain,
        has_certificate = true,
        has_chain = data.chain ~= nil,
        meta = data.meta
    }))
end

function exports.create_certificate()
    local data = read_json_body()
    if not data then
        return
    end

    local required_fields = { "domain", "certificate", "private_key" }
    
    for _, field in ipairs(required_fields) do
        if not data[field] then
            local err = { detail = "The '" .. field .. "' field is required." }
            ngx.status = 400
            ngx.say(cjson.encode(err))
            return
        end
    end

    local meta = data.meta or {}
    local success = certificates.storeCertificate(
        data.domain,
        data.certificate,
        data.private_key,
        data.chain,
        meta
    )

    if not success then
        ngx.log(ngx.ERR, "Failed to store certificate for " .. data.domain)
        local err = { detail = "Failed to store certificate" }
        ngx.status = 500
        ngx.say(cjson.encode(err))
        return
    end

    ngx.status = 201
    ngx.say(cjson.encode({
        domain = data.domain,
        has_certificate = true,
        has_chain = data.chain ~= nil,
        meta = meta
    }))
end

-- Update the certificate stored for this domain. The URL names the
-- certificate; certificate and private_key are replaced together, and a
-- replaced certificate takes the request's chain (or none).
function exports.update_certificate(domain)
    local existing = certificates.getStoredCertificate(domain)

    if not existing then
        ngx.status = 404
        ngx.say(cjson.encode({detail = "No certificate found for " .. domain}))
        return
    end

    local data = read_json_body()
    if not data then
        return
    end

    if is_set(data.domain) and data.domain ~= domain then
        bad_request("The 'domain' field must match the certificate in the URL.")
        return
    end

    if is_set(data.certificate) ~= is_set(data.private_key) then
        bad_request("The 'certificate' and 'private_key' fields must be provided together.")
        return
    end

    local certificate = existing.certificate
    local private_key = existing.key
    local chain = existing.chain
    if is_set(data.certificate) then
        certificate = data.certificate
        private_key = data.private_key
        chain = is_set(data.chain) and data.chain or nil
    end

    local meta = existing.meta or {}
    if is_set(data.meta) then
        meta = data.meta
    end

    local success = certificates.storeCertificate(domain, certificate, private_key, chain, meta)

    if not success then
        ngx.log(ngx.ERR, "Failed to update certificate for " .. domain)
        ngx.status = 500
        ngx.say(cjson.encode({detail = "Failed to update certificate"}))
        return
    end

    ngx.say(cjson.encode({
        domain = domain,
        has_certificate = true,
        has_chain = chain ~= nil,
        meta = meta
    }))
end

function exports.delete_certificate(domain)
    local success = certificates.deleteCertificate(domain)

    if success then
        ngx.status = 204
        return
    end

    ngx.status = 500
    ngx.say(cjson.encode({detail = "Failed to delete certificate"}))
end

return exports

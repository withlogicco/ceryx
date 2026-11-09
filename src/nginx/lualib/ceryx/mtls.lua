--[[
    Ceryx mTLS policy

    Routes require client certificates with their own mtls_* settings. A route
    without a trusted CA or verify depth of its own uses
    CERYX_MTLS_DEFAULT_TRUSTED_CA and CERYX_MTLS_DEFAULT_VERIFY_DEPTH, read
    when a request arrives, so changing them applies to those routes.
]]

local settings = require "ceryx.settings"
local utils = require "ceryx.utils"

local exports = {}

exports.FIELDS = {
    "mtls_require_client_certificate",
    "mtls_trusted_ca",
    "mtls_verify_depth"
}

local function is_unset(value)
    return value == nil or value == ngx.null or value == ""
end

-- true or false, or nil when value isn't one (stored values may be strings).
local function to_boolean(value)
    if type(value) == "boolean" then
        return value
    end

    if type(value) == "string" then
        local lowered = value:lower()
        if lowered == "true" then
            return true
        end
        if lowered == "false" then
            return false
        end
    end

    return nil
end

-- A whole number of 0 or more, or nil.
local function to_depth(value)
    local number = tonumber(value)

    if number and number >= 0 and number == math.floor(number) then
        return number
    end

    return nil
end

local function is_readable(path)
    local file = io.open(path, "r")

    if not file then
        return false
    end

    file:close()
    return true
end

exports.to_boolean = to_boolean
exports.to_depth = to_depth
exports.is_readable = is_readable

--- The policy from a route's mtls_* settings, with the defaults for a
-- trusted CA and verify depth it doesn't set.
-- @return {require_client_certificate, trusted_ca, verify_depth, error}, where
-- error names a CERYX_MTLS_DEFAULT_* variable with an unusable value
function exports.resolve(route_settings)
    route_settings = route_settings or {}

    local policy = {
        require_client_certificate = to_boolean(route_settings.mtls_require_client_certificate) == true
    }

    policy.trusted_ca = route_settings.mtls_trusted_ca
    if is_unset(policy.trusted_ca) then
        policy.trusted_ca = utils.getenv("CERYX_MTLS_DEFAULT_TRUSTED_CA", nil)
        if policy.trusted_ca and not is_readable(policy.trusted_ca) then
            policy.error = "CERYX_MTLS_DEFAULT_TRUSTED_CA (" .. policy.trusted_ca .. ") is not readable."
        end
    end

    local verify_depth = route_settings.mtls_verify_depth
    if is_unset(verify_depth) then
        verify_depth = utils.getenv("CERYX_MTLS_DEFAULT_VERIFY_DEPTH", nil)
        if verify_depth and to_depth(verify_depth) == nil then
            policy.error = "CERYX_MTLS_DEFAULT_VERIFY_DEPTH must be a whole number of 0 or more, not '" .. verify_depth .. "'."
        end
    end
    policy.verify_depth = to_depth(verify_depth)

    return policy
end

--- The policy for requests to host: its route's, or $wildcard's for a host
-- without a route of its own.
function exports.policy_for_host(host)
    return exports.resolve(settings.getSettingsForHost(host, exports.FIELDS, true))
end

--- Check a route's settings before they are saved.
-- @param route_settings The complete settings the route will have
-- @return true; or false, an error message and a status: 400 for the route's
-- settings, 500 for an unusable CERYX_MTLS_DEFAULT_* variable
function exports.validate(route_settings)
    route_settings = route_settings or {}

    local require_client_certificate = route_settings.mtls_require_client_certificate
    if not is_unset(require_client_certificate) and to_boolean(require_client_certificate) == nil then
        return false, "mtls_require_client_certificate must be true or false.", 400
    end

    local trusted_ca = route_settings.mtls_trusted_ca
    if not is_unset(trusted_ca) and (type(trusted_ca) ~= "string" or not is_readable(trusted_ca)) then
        return false, "mtls_trusted_ca must be the path of a readable CA bundle.", 400
    end

    local verify_depth = route_settings.mtls_verify_depth
    if not is_unset(verify_depth) and to_depth(verify_depth) == nil then
        return false, "mtls_verify_depth must be a whole number of 0 or more.", 400
    end

    if to_boolean(require_client_certificate) ~= true then
        return true
    end

    local policy = exports.resolve(route_settings)
    if policy.error then
        return false, policy.error, 500
    end

    if is_unset(policy.trusted_ca) then
        return false, "The route requires client certificates, so it needs mtls_trusted_ca, or CERYX_MTLS_DEFAULT_TRUSTED_CA must be set.", 400
    end

    if to_boolean(route_settings.enforce_https) ~= true then
        return false, "enforce_https must be true when the route requires client certificates.", 400
    end

    return true
end

return exports

local certificates = require "ceryx.certificates"
local ssl = require "ngx.ssl"
local redis = require "ceryx.redis"
local utils = require "ceryx.utils"

local disable_lets_encrypt = utils.getenv("CERYX_DISABLE_LETS_ENCRYPT", ""):lower() == "true"
local host, host_err = ssl.server_name()

if not host then
    ngx.log(ngx.ERROR, "Could not retrieve SSL Server Name: " .. host_err)
    return ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
end

local host_certificates = certificates.getCertificatesForHost(host)

if certificates ~= nil then
    -- Convert data from PEM to DER
    local certificate_der, certificate_der_err = ssl.cert_pem_to_der(host_certificates["certificate"])
    if not certificate_der or certificate_der_err then
        ngx.log(ngx.ERROR, "Could not convert SSL Certificate to DER. Error: " .. (certificate_der_err or ""))
        ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
    end

    local key_der, key_der_err = ssl.priv_key_pem_to_der(host_certificates["key"])
    if not key_der or key_der_err then
        ngx.log(ngx.ERROR, "Could not convert PEM key to DER. Error: " .. (key_der_err or ""))
        ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
    end

    -- Set the certificate information for the current SSL Session
    local ssl_certificate_ok, ssl_certficate_error = ssl.set_der_cert(certificate_der)

    if not ssl_certificate_ok then
        ngx.log(
            ngx.ERROR,
            "Could not set the certificate for the current SSL Session. Error: " .. (ssl_certficate_error or "")
        )
        ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
    end

    local ssl_key_ok, ssl_key_error = ssl.set_der_priv_key(key_der)
    if not ssl_key_ok then
        ngx.log(ngx.ERROR, "Could not set the key for the current SSL Session. Error: " .. (ssl_key_error or ""))
        ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
    end
else
    ngx.log(ngx.INFO, "No valid SSL certificate has been configured for " .. host .. ".")

    if not disable_lets_encrypt then
        ngx.log(ngx.INFO, "Passing SSL certificate handling for " .. host .. " to Let's Encrypt.")
        auto_ssl:ssl_certificate()
    end
end

ngx.log(ngx.DEBUG, "Completed SSL negotiation for " .. host)

local ssl = require "ngx.ssl"
local get_redis_client = require "redis_client"

local domain, err = ssl.server_name()
local red = get_redis_client()

local prefix = os.getenv("CERYX_REDIS_PREFIX")
if not prefix then prefix = "ceryx" end

ngx.log(ngx.STDERR, "Searching for SSL Certificate for " .. domain)

local certificate_key = prefix .. ":certificates:" .. domain
local certificate, err = red:hgetall(certificate_key)

if err then
    ngx.log(ngx.STDERR, "Redis error: " .. err)
    ngx.exit()
end

-- Check if "certificate" is an empty table
if next(certificate) ~= nil then
    ngx.log(ngx.STDERR, "Found SSL Certificate for " .. domain .. " in Redis. Using this.")

    local path_to_bundle = certificate[2]
    local path_to_key = certificate[4]

    ngx.log(ngx.STDERR, path_to_bundle)
    ngx.log(ngx.STDERR, path_to_key)

    local bundle_file = assert(io.open(path_to_bundle, "r"))
    local bundle_data = bundle_file:read("*all")
    bundle_file:close()

    local key_file = assert(io.open(path_to_key, "r"))
    local key_data = key_file:read("*all")
    key_file:close()

    -- Convert data from PEM to DER
    local bundle_der, bundle_der_err = ssl.cert_pem_to_der(bundle_data)
    if not bundle_der or bundle_der_err then
	ngx.log(ngx.STDERR, "Could not convert PEM bundle to DER. Error: " .. (bundle_der_err or ""))
	ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
    end

    local key_der, key_der_err = ssl.priv_key_pem_to_der(key_data)
    if not key_der or key_der_err then
	ngx.log(ngx.STDERR, "Could not convert PEM key to DER. Error: " .. (key_der_err or ""))
	ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
    end

    -- Set the certificate information for the current SSL Session
    local session_bundle_ok, session_bundle_err = ssl.set_der_cert(bundle_der)
    if not session_bundle_ok then
	ngx.log(ngx.STDERR, "Could not set the certificate for the current SSL Session. Error: " .. (session_bundle_err or ""))
	ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
    end

    local session_key_ok, session_key_err = ssl.set_der_priv_key(key_der)
    if not session_key_ok then
	ngx.log(ngx.STDERR, "Could not set the key for the current SSL Session. Error: " .. (session_key_err or ""))
	ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
    end
else
    ngx.log(ngx.STDERR, "Did not find SSL Certificate for " .. domain .. " in Redis. Using to automatic Let's Encrypt.")
    auto_ssl:ssl_certificate()
end

ngx.log(ngx.STDERR, "Completed SSL negotiation for " .. domain)

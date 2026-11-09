--[[
    Ceryx Certificates Module
    
    Handles SSL/TLS certificate lookups using the storage abstraction layer.
    Supports both Redis and SQLite backends transparently.
    
    Certificates can be stored in two ways:
    1. File paths (legacy): route settings contain certificate_path and key_path
    2. JWK format (new): stored directly in storage with cert/key/chain/meta
    
    The JWK format stores certificates as:
    - kind: 'certificate'
    - key: domain name
    - value: JSON with {certificate, private_key, chain}
    - meta: {vendor, issued_at, expires_at, san}
]]

local cjson = require "cjson"
local ssl = require "ngx.ssl"
local settings = require "ceryx.settings"
local storage = require "ceryx.storage"
local utils = require "ceryx.utils"

-- Legacy module for backward compatibility
local redis_ok, redis = pcall(require, "ceryx.redis")

local exports = {}
local settings_fields = {"certificate_path", "key_path"}

--- Legacy: Get Redis key for host (backward compatibility)
function getRedisKeyForHost(host)
    if redis_ok then
        return redis.prefix .. ":settings:" .. host
    end
    return "ceryx:settings:" .. host
end

--- Get certificates from JWK storage
-- @param host The hostname
-- @param fallback_to_wildcard Try *.parent when there is no exact match (default true)
-- @return data table {certificate, key} or nil
local function getCertificatesFromStorage(host, fallback_to_wildcard)
    local cert_data, meta = storage.get_certificate(host, fallback_to_wildcard)
    
    if not cert_data then
        return nil
    end
    
    -- Parse JWK format
    local cert_bundle
    if type(cert_data) == "string" then
        local ok, parsed = pcall(cjson.decode, cert_data)
        if ok then
            cert_bundle = parsed
        else
            ngx.log(ngx.ERR, "Failed to parse certificate data for " .. host)
            return nil
        end
    else
        cert_bundle = cert_data
    end
    
    if not cert_bundle.certificate or not cert_bundle.private_key then
        ngx.log(ngx.ERR, "Invalid certificate bundle format for " .. host)
        return nil
    end
    
    return {
        certificate = cert_bundle.certificate,
        key = cert_bundle.private_key,
        chain = cert_bundle.chain,
        meta = meta
    }
end

--- Get certificates from file paths (legacy method)
-- @param host The hostname
-- @return data table {certificate, key} or nil
local function getCertificatesFromFiles(host)
    local host_settings = settings.getSettingsForHost(host, settings_fields, true)

    if host_settings == nil then
        return nil
    end

    local certificate_path = host_settings.certificate_path
    local key_path = host_settings.key_path
    
    if not certificate_path or certificate_path == "" or certificate_path == ngx.null then
        return nil
    end
    
    if not key_path or key_path == "" or key_path == ngx.null then
        return nil
    end
    
    ngx.log(ngx.DEBUG, "Loading SSL certificates for " .. host .. " from files.")
    
    local certificate_data = utils.read_file(certificate_path)
    local key_data = utils.read_file(key_path)
    
    if not certificate_data or not key_data then
        ngx.log(ngx.ERR, "Failed to read certificate files for " .. host)
        return nil
    end
    
    return {
        certificate = certificate_data,
        key = key_data
    }
end

--- Get certificates for a host
-- First tries JWK storage, then falls back to file paths
-- @param host The hostname
-- @return data table {certificate, key} or nil
function getCertificatesForHost(host)
    ngx.log(ngx.DEBUG, "Looking for SSL certificate for " .. host)
    
    -- Try JWK storage first
    local data = getCertificatesFromStorage(host)
    
    if data then
        ngx.log(ngx.DEBUG, "Found SSL certificate for " .. host .. " in storage.")
        return data
    end
    
    -- Fall back to file paths
    data = getCertificatesFromFiles(host)
    
    if data then
        ngx.log(ngx.DEBUG, "Found SSL certificate for " .. host .. " from files.")
        return data
    end
    
    ngx.log(ngx.DEBUG, "No SSL certificate found for " .. host)
    return nil
end

--- Get the certificate stored for exactly this host (no wildcard or file fallback)
-- @param host The hostname
-- @return data table {certificate, key, chain, meta} or nil
function getStoredCertificate(host)
    return getCertificatesFromStorage(host, false)
end

--- Store a certificate for a host (JWK format)
-- @param host The hostname
-- @param certificate PEM-encoded certificate
-- @param key PEM-encoded private key
-- @param chain Optional PEM-encoded certificate chain
-- @param meta Optional metadata {vendor, san, expires_at}
-- @return boolean success
function storeCertificate(host, certificate, key, chain, meta)
    local cert_bundle = {
        certificate = certificate,
        private_key = key,
        chain = chain
    }
    
    meta = meta or {}
    meta.stored_at = os.time()
    
    return storage.set_certificate(host, cjson.encode(cert_bundle), meta)
end

--- Delete a certificate for a host
-- @param host The hostname
-- @return boolean success
function deleteCertificate(host)
    return storage.delete_certificate(host)
end

--- List all certificates
-- @return Array of certificate records
function listCertificates()
    return storage.list_certificates()
end

--- Check if a certificate exists for a host
-- @param host The hostname
-- @return boolean
function hasCertificate(host)
    local data = getCertificatesFromStorage(host)
    if data then
        return true
    end
    
    data = getCertificatesFromFiles(host)
    return data ~= nil
end

-- Exports
exports.getCertificatesForHost = getCertificatesForHost
exports.getStoredCertificate = getStoredCertificate
exports.storeCertificate = storeCertificate
exports.deleteCertificate = deleteCertificate
exports.listCertificates = listCertificates
exports.hasCertificate = hasCertificate
exports.getRedisKeyForHost = getRedisKeyForHost  -- Legacy

return exports

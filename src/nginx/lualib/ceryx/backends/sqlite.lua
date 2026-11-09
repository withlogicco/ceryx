--[[
    Ceryx SQLite Storage Backend
    
    Implements the storage interface using SQLite with:
    - Memory mapping (mmap) for performance
    - WAL journal mode for concurrent access
    - Configurable connection pooling (per-worker or per-request)
    
    Environment Variables:
    - CERYX_SQLITE_PATH: Database file path (default: /var/lib/ceryx/ceryx.db)
    - CERYX_SQLITE_MMAP_SIZE: Memory map size in bytes (default: 1073741824 / 1GB)
    - CERYX_SQLITE_WAL_MODE: Enable WAL journal mode (default: true)
    - CERYX_SQLITE_POOL_MODE: Connection pooling - 'worker' (default) or 'request'
]]

local utils = require "ceryx.utils"
local cjson = require "cjson"

-- Try to load lsqlite3
local sqlite3
local ok, err = pcall(function()
    sqlite3 = require "lsqlite3"
end)

if not ok then
    -- Fallback to standard sqlite3 module
    ok, err = pcall(function()
        sqlite3 = require "sqlite3"
    end)
    
    if not ok then
        ngx.log(ngx.ERR, "Failed to load SQLite module: ", err)
        error("SQLite module not available. Install lsqlite3 or sqlite3.")
    end
end

local SqliteBackend = {}
SqliteBackend.__index = SqliteBackend

-- Configuration from environment
local DB_PATH = utils.getenv("CERYX_SQLITE_PATH", "/var/lib/ceryx/ceryx.db")
local MMAP_SIZE = tonumber(utils.getenv("CERYX_SQLITE_MMAP_SIZE", "1073741824"))  -- 1GB default
local WAL_MODE = utils.getenv("CERYX_SQLITE_WAL_MODE", "true") == "true"
local POOL_MODE = utils.getenv("CERYX_SQLITE_POOL_MODE", "worker")  -- 'worker' or 'request'

-- Worker-level connection cache (for POOL_MODE = 'worker')
local _worker_db = nil

--- Create a new SQLite backend instance
-- @return SqliteBackend instance
function SqliteBackend.new()
    local self = setmetatable({}, SqliteBackend)
    self.db = nil
    return self
end

--- Get or create database connection
-- @return database connection
function SqliteBackend:get_connection()
    if POOL_MODE == "worker" then
        -- Reuse worker-level connection
        if _worker_db then
            return _worker_db
        end
        
        _worker_db = self:open_connection()
        return _worker_db
    else
        -- Per-request connection
        if not self.db then
            self.db = self:open_connection()
        end
        return self.db
    end
end

--- Open a new database connection with optimized settings
-- @return database connection
function SqliteBackend:open_connection()
    local db, err = sqlite3.open(DB_PATH)
    
    if not db then
        ngx.log(ngx.ERR, "Failed to open SQLite database: ", err or "unknown error")
        return nil
    end
    
    -- Apply performance pragmas
    db:exec("PRAGMA mmap_size = " .. MMAP_SIZE)
    db:exec("PRAGMA cache_size = -64000")  -- 64MB cache
    db:exec("PRAGMA temp_store = MEMORY")
    db:exec("PRAGMA synchronous = NORMAL")
    
    if WAL_MODE then
        db:exec("PRAGMA journal_mode = WAL")
    end
    
    -- Enable foreign keys (good practice)
    db:exec("PRAGMA foreign_keys = ON")
    
    ngx.log(ngx.DEBUG, "SQLite connection opened: ", DB_PATH, 
            " mmap_size=", MMAP_SIZE, 
            " wal=", tostring(WAL_MODE),
            " pool_mode=", POOL_MODE)
    
    return db
end

--- Initialize database schema
-- @return boolean success
function SqliteBackend:init()
    local db = self:get_connection()
    if not db then
        return false
    end
    
    -- Create resource table matching benchmark schema
    local create_sql = [[
        CREATE TABLE IF NOT EXISTS resource (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            meta TEXT,
            UNIQUE(kind, key)
        )
    ]]
    
    local result = db:exec(create_sql)
    if result ~= sqlite3.OK then
        ngx.log(ngx.ERR, "Failed to create resource table: ", db:errmsg())
        return false
    end
    
    -- Create indexes for efficient lookups
    db:exec("CREATE INDEX IF NOT EXISTS idx_kind ON resource(kind)")
    db:exec("CREATE INDEX IF NOT EXISTS idx_key ON resource(key)")
    db:exec("CREATE INDEX IF NOT EXISTS idx_kind_key ON resource(kind, key)")
    
    ngx.log(ngx.INFO, "SQLite database initialized: ", DB_PATH)
    return true
end

--- Get a record by kind and key
-- @param kind The record kind (e.g., 'route', 'certificate')
-- @param key The record key (e.g., hostname, domain)
-- @return value, meta_table or nil
function SqliteBackend:get(kind, key)
    local db = self:get_connection()
    if not db then
        return nil, nil
    end
    
    local stmt = db:prepare("SELECT value, meta FROM resource WHERE kind = ? AND key = ?")
    if not stmt then
        ngx.log(ngx.ERR, "Failed to prepare SELECT statement: ", db:errmsg())
        return nil, nil
    end
    
    stmt:bind_values(kind, key)
    
    local result = stmt:step()
    if result == sqlite3.ROW then
        local value = stmt:get_value(0)
        local meta_json = stmt:get_value(1)
        stmt:finalize()
        
        local meta = {}
        if meta_json and meta_json ~= "" then
            local ok, decoded = pcall(cjson.decode, meta_json)
            if ok then
                meta = decoded
            end
        end
        
        return value, meta
    end
    
    stmt:finalize()
    return nil, nil
end

--- Set a record (insert or update)
-- @param kind The record kind
-- @param key The record key
-- @param value The record value
-- @param meta Table of metadata (will be JSON encoded)
-- @return boolean success
function SqliteBackend:set(kind, key, value, meta)
    local db = self:get_connection()
    if not db then
        return false
    end
    
    local meta_json = "{}"
    if meta and next(meta) then
        local ok, encoded = pcall(cjson.encode, meta)
        if ok then
            meta_json = encoded
        end
    end
    
    -- Use INSERT OR REPLACE for upsert behavior
    local stmt = db:prepare([[
        INSERT OR REPLACE INTO resource (kind, key, value, meta)
        VALUES (?, ?, ?, ?)
    ]])
    
    if not stmt then
        ngx.log(ngx.ERR, "Failed to prepare INSERT statement: ", db:errmsg())
        return false
    end
    
    stmt:bind_values(kind, key, value, meta_json)
    
    local result = stmt:step()
    stmt:finalize()
    
    if result ~= sqlite3.DONE then
        ngx.log(ngx.ERR, "Failed to insert/update record: ", db:errmsg())
        return false
    end
    
    return true
end

--- Delete a record
-- @param kind The record kind
-- @param key The record key
-- @return boolean success
function SqliteBackend:delete(kind, key)
    local db = self:get_connection()
    if not db then
        return false
    end
    
    local stmt = db:prepare("DELETE FROM resource WHERE kind = ? AND key = ?")
    if not stmt then
        ngx.log(ngx.ERR, "Failed to prepare DELETE statement: ", db:errmsg())
        return false
    end
    
    stmt:bind_values(kind, key)
    
    local result = stmt:step()
    stmt:finalize()
    
    if result ~= sqlite3.DONE then
        ngx.log(ngx.ERR, "Failed to delete record: ", db:errmsg())
        return false
    end
    
    return true
end

--- List all records of a specific kind
-- @param kind The record kind
-- @return array of {key, value, meta}
function SqliteBackend:list(kind)
    local db = self:get_connection()
    if not db then
        return {}
    end
    
    local results = {}
    local stmt = db:prepare("SELECT key, value, meta FROM resource WHERE kind = ?")
    
    if not stmt then
        ngx.log(ngx.ERR, "Failed to prepare SELECT statement: ", db:errmsg())
        return {}
    end
    
    stmt:bind_values(kind)
    
    while stmt:step() == sqlite3.ROW do
        local key = stmt:get_value(0)
        local value = stmt:get_value(1)
        local meta_json = stmt:get_value(2)
        
        local meta = {}
        if meta_json and meta_json ~= "" then
            local ok, decoded = pcall(cjson.decode, meta_json)
            if ok then
                meta = decoded
            end
        end
        
        table.insert(results, {
            key = key,
            value = value,
            meta = meta
        })
    end
    
    stmt:finalize()
    return results
end

--- Check if a record exists
-- @param kind The record kind
-- @param key The record key
-- @return boolean
function SqliteBackend:exists(kind, key)
    local db = self:get_connection()
    if not db then
        return false
    end
    
    local stmt = db:prepare("SELECT 1 FROM resource WHERE kind = ? AND key = ? LIMIT 1")
    if not stmt then
        return false
    end
    
    stmt:bind_values(kind, key)
    
    local result = stmt:step()
    stmt:finalize()
    
    return result == sqlite3.ROW
end

--- Get record with fallback to another key
-- @param kind The record kind
-- @param key The primary key
-- @param fallback_key The fallback key if primary not found
-- @return value, meta_table or nil
function SqliteBackend:get_with_fallback(kind, key, fallback_key)
    local value, meta = self:get(kind, key)
    if value then
        return value, meta
    end
    
    return self:get(kind, fallback_key)
end

--- Close the database connection
function SqliteBackend:close()
    if self.db then
        self.db:close()
        self.db = nil
    end
    
    -- Don't close worker-level connection here
    -- It will be reused for other requests
end

--- Force close all connections (for cleanup/shutdown)
function SqliteBackend.close_all()
    if _worker_db then
        _worker_db:close()
        _worker_db = nil
    end
end

--- Get database statistics
-- @return table with stats
function SqliteBackend:stats()
    local db = self:get_connection()
    if not db then
        return {}
    end
    
    local stats = {
        path = DB_PATH,
        mmap_size = MMAP_SIZE,
        wal_mode = WAL_MODE,
        pool_mode = POOL_MODE
    }
    
    -- Count records by kind
    local stmt = db:prepare("SELECT kind, COUNT(*) FROM resource GROUP BY kind")
    if stmt then
        while stmt:step() == sqlite3.ROW do
            local kind = stmt:get_value(0)
            local count = stmt:get_value(1)
            stats[kind .. "_count"] = count
        end
        stmt:finalize()
    end
    
    return stats
end

return SqliteBackend

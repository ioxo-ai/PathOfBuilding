-- Standalone MCP Server Test
-- Tests protocol layer without PathOfBuilding initialization

-- Set package path
package.path = package.path .. ";runtime/lua/?.lua;runtime/lua/?/init.lua"

-- Load MCP server
local mcpServer = dofile("mcp-server/init.lua")
mcpServer.DEBUG = true

-- Initialize stub handlers
mcpServer.initializeStubHandlers()

-- Run server
mcpServer.run()

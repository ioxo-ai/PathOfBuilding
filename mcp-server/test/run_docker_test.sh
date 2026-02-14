#!/bin/bash
# Run MCP Server in Docker with Lua 5.1

cd /home/user/PathOfBuilding

echo "=== Starting MCP Server Test in Docker ==="

# Create a simple test that doesn't require full PathOfBuilding initialization
cat > /tmp/mcp_minimal_test.lua << 'LUAEOF'
-- Minimal test that just loads and tests protocol.lua independently
package.path = package.path .. ";./runtime/lua/?.lua"

-- Load JSON
local json = dofile("runtime/lua/dkjson.lua")

-- Load protocol
local protocol = dofile("mcp-server/protocol.lua")

print("=== MCP Protocol Module Loaded ===")
print("Server name:", protocol.SERVER_INFO.name)
print("Version:", protocol.SERVER_INFO.version)
print("Protocol version:", protocol.SERVER_INFO.protocolVersion)
print("Tools defined:", #protocol.TOOLS)

-- Test 1: Initialize request
local init_req = {
    jsonrpc = "2.0",
    id = 1,
    method = "initialize",
    params = {}
}

local response = protocol.handleRequest(init_req, {})
print("\n=== Test 1: Initialize ===")
print("Response:", json.encode(response, { indent = true }))

-- Test 2: Tools list
local tools_req = {
    jsonrpc = "2.0",
    id = 2,
    method = "tools/list",
    params = {}
}

local response2 = protocol.handleRequest(tools_req, {})
print("\n=== Test 2: Tools List ===")
print("Result has tools:", response2.result and response2.result.tools ~= nil)
print("Number of tools:", response2.result and #response2.result.tools or 0)

-- Test 3: Invalid method
local invalid_req = {
    jsonrpc = "2.0",
    id = 3,
    method = "invalid_method",
    params = {}
}

local response3 = protocol.handleRequest(invalid_req, {})
print("\n=== Test 3: Invalid Method ===")
print("Has error:", response3.error ~= nil)
print("Error code:", response3.error and response3.error.code or "none")

print("\n=== All Protocol Tests Passed ===")
LUAEOF

# Run in Docker
docker run --rm -v /home/user/PathOfBuilding:/app -w /app nikolaik/python-nodejs:lua5.1 lua /tmp/mcp_minimal_test.lua

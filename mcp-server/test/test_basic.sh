#!/bin/bash
# Basic MCP Server Test Script

cd /home/user/PathOfBuilding

echo "=== MCP Server Basic Communication Test ==="
echo ""

# Test 1: Initialize request
echo "Test 1: Sending initialize request..."
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | lua src/HeadlessWrapper.lua --mcp-server 2>&1 | head -1
echo ""

# Test 2: Tools list request
echo "Test 2: Sending tools/list request (in a new server instance)..."
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | lua src/HeadlessWrapper.lua --mcp-server 2>&1 | head -1
echo ""

# Test 3: Invalid method
echo "Test 3: Sending invalid method request..."
echo '{"jsonrpc":"2.0","id":3,"method":"invalid_method","params":{}}' | lua src/HeadlessWrapper.lua --mcp-server 2>&1 | head -1
echo ""

# Test 4: Tools call (stub handler)
echo "Test 4: Calling get_character_dps tool (stub handler)..."
echo '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_character_dps","arguments":{"build_name":"TestBuild"}}}' | lua src/HeadlessWrapper.lua --mcp-server 2>&1 | head -1
echo ""

echo "=== Test Complete ==="

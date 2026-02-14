-- Path of Building
--
-- Module: MCP Server Main
-- Main entry point for the MCP server
--

local json = require("dkjson")
local protocol = dofile("mcp-server/protocol.lua")

local mcpServer = {}

-- Debug mode flag
mcpServer.DEBUG = false

-- Log function (writes to stderr to not interfere with stdout JSON-RPC)
function mcpServer.log(...)
	if mcpServer.DEBUG then
		io.stderr:write("[MCP-SERVER] ")
		io.stderr:write(table.concat({...}, " "))
		io.stderr:write("\n")
		io.stderr:flush()
	end
end

-- Tool handlers (to be set by the caller)
mcpServer.toolHandlers = {}

-- Register a tool handler
function mcpServer.registerToolHandler(toolName, handler)
	mcpServer.toolHandlers[toolName] = handler
	mcpServer.log("Registered handler for tool:", toolName)
end

-- Send JSON-RPC response to stdout
function mcpServer.sendResponse(response)
	local jsonStr = json.encode(response)
	io.stdout:write(jsonStr)
	io.stdout:write("\n")
	io.stdout:flush()
	mcpServer.log("Sent response:", jsonStr:sub(1, 200))
end

-- Read one line from stdin
function mcpServer.readLine()
	local line = io.stdin:read("*l")
	if line then
		mcpServer.log("Received request:", line:sub(1, 200))
	end
	return line
end

-- Main server loop
function mcpServer.run()
	mcpServer.log("MCP Server starting...")
	mcpServer.log("Protocol version:", protocol.SERVER_INFO.protocolVersion)
	mcpServer.log("Registered tools:", #protocol.TOOLS)

	while true do
		local line = mcpServer.readLine()

		if not line then
			-- EOF reached, exit gracefully
			mcpServer.log("EOF received, shutting down...")
			break
		end

		-- Skip empty lines
		if line:match("^%s*$") then
			mcpServer.log("Skipping empty line")
			goto continue
		end

		-- Handle the request
		local response = protocol.handleRequest(line, mcpServer.toolHandlers)
		mcpServer.sendResponse(response)

		::continue::
	end

	mcpServer.log("MCP Server stopped.")
end

-- Initialize with default stub handlers
function mcpServer.initializeStubHandlers()
	mcpServer.log("Initializing stub handlers for testing...")

	mcpServer.registerToolHandler("get_character_dps", function(args)
		mcpServer.log("Stub: get_character_dps called with:", json.encode(args))
		return {
			character = {
				name = args.build_name,
				level = 1,
				class = "Unknown",
				ascendancy = "None"
			},
			config = {
				boss_type = args.boss_type or "None",
				calculation_mode = args.calculation_mode or "EFFECTIVE"
			},
			dps = {
				total_dps = 0,
				combined_dps = 0,
				total_dot_dps = 0,
				average_hit = 0,
				ailments = {
					ignite_dps = 0,
					poison_dps = 0,
					bleed_dps = 0,
					total_poison_stacks = 0
				},
				speed = {
					attack_rate = 0,
					cast_rate = 0,
					hit_chance = 0
				}
			},
			defense = {
				life = 0,
				energy_shield = 0,
				mana = 0,
				total_pool = 0,
				evasion = 0,
				evasion_chance = 0,
				armor = 0,
				physical_reduction = 0,
				block_chance = 0,
				spell_block_chance = 0,
				resistances = {
					fire = 0,
					cold = 0,
					lightning = 0,
					chaos = 0
				},
				ehp = {
					physical = 0,
					elemental = 0,
					chaos = 0
				}
			},
			active_skill = {
				name = "None",
				socket_group = 1,
				skill_type = "Unknown",
				mana_cost = 0,
				skill_part = "Default"
			}
		}
	end)

	mcpServer.registerToolHandler("simulate_equipment_change", function(args)
		mcpServer.log("Stub: simulate_equipment_change called with:", json.encode(args))
		return {
			before = {
				item_name = "Current Item",
				item_rarity = "Unknown"
			},
			after = {
				item_name = "New Item",
				item_rarity = "Unknown"
			},
			delta = {
				dps = {},
				defense = {}
			}
		}
	end)

	mcpServer.registerToolHandler("list_builds", function(args)
		mcpServer.log("Stub: list_builds called")
		return {
			builds = {}
		}
	end)

	mcpServer.registerToolHandler("compare_items", function(args)
		mcpServer.log("Stub: compare_items called with:", json.encode(args))
		return {
			current = {},
			comparisons = {}
		}
	end)
end

return mcpServer

-- Path of Building
--
-- Module: MCP Protocol Handler
-- Implements JSON-RPC 2.0 protocol for Model Context Protocol (MCP)
--

-- Load JSON library
local json = dofile("runtime/lua/dkjson.lua")

local protocol = {}

-- MCP Server Information
protocol.SERVER_INFO = {
	name = "pathofbuilding-mcp-server",
	version = "1.0.0",
	protocolVersion = "2024-11-05"
}

-- MCP Capabilities
protocol.CAPABILITIES = {
	tools = {}
}

-- Tool Definitions
protocol.TOOLS = {
	{
		name = "get_character_dps",
		description = "지정된 빌드의 현재 DPS 및 방어 통계를 반환합니다. 보스별 DPS 계산, 여러 스킬 처리 지원.",
		inputSchema = {
			type = "object",
			properties = {
				build_name = {
					type = "string",
					description = "빌드 파일명 또는 경로"
				},
				skill_index = {
					type = {"number", "string"},
					description = "계산할 스킬 그룹 인덱스 (1~N) 또는 'all' (기본값: 1)"
				},
				boss_type = {
					type = "string",
					enum = {"None", "Boss", "Pinnacle", "Uber"},
					description = "보스 타입 (기본값: 'None')"
				},
				calculation_mode = {
					type = "string",
					enum = {"UNBUFFED", "BUFFED", "COMBAT", "EFFECTIVE"},
					description = "계산 모드 (기본값: 'EFFECTIVE')"
				}
			},
			required = {"build_name"}
		}
	},
	{
		name = "simulate_equipment_change",
		description = "특정 슬롯의 장비를 교체했을 때 DPS 및 방어력 변화를 계산합니다.",
		inputSchema = {
			type = "object",
			properties = {
				build_name = {
					type = "string",
					description = "빌드 파일명 또는 경로"
				},
				slot = {
					type = "string",
					description = "장비 슬롯 (예: 'Weapon 1', 'Helmet', 'Body Armour')"
				},
				item_text = {
					type = "string",
					description = "게임에서 복사한 아이템 텍스트"
				},
				keep_changes = {
					type = "boolean",
					description = "true면 빌드에 영구 적용 (기본값: false)"
				},
				boss_type = {
					type = "string",
					enum = {"None", "Boss", "Pinnacle", "Uber"},
					description = "보스 타입 (기본값: 'None')"
				},
				calculation_mode = {
					type = "string",
					enum = {"UNBUFFED", "BUFFED", "COMBAT", "EFFECTIVE"},
					description = "계산 모드 (기본값: 'EFFECTIVE')"
				}
			},
			required = {"build_name", "slot", "item_text"}
		}
	},
	{
		name = "list_builds",
		description = "사용 가능한 빌드 목록을 반환합니다.",
		inputSchema = {
			type = "object",
			properties = {}
		}
	},
	{
		name = "compare_items",
		description = "여러 아이템을 동시에 비교합니다 (동일 슬롯).",
		inputSchema = {
			type = "object",
			properties = {
				build_name = {
					type = "string",
					description = "빌드 파일명 또는 경로"
				},
				slot = {
					type = "string",
					description = "장비 슬롯"
				},
				items = {
					type = "array",
					items = {
						type = "string"
					},
					description = "비교할 아이템들의 텍스트 배열"
				},
				boss_type = {
					type = "string",
					enum = {"None", "Boss", "Pinnacle", "Uber"},
					description = "보스 타입 (기본값: 'None')"
				},
				calculation_mode = {
					type = "string",
					enum = {"UNBUFFED", "BUFFED", "COMBAT", "EFFECTIVE"},
					description = "계산 모드 (기본값: 'EFFECTIVE')"
				}
			},
			required = {"build_name", "slot", "items"}
		}
	}
}

-- JSON-RPC Error Codes
protocol.ERROR_CODES = {
	PARSE_ERROR = -32700,
	INVALID_REQUEST = -32600,
	METHOD_NOT_FOUND = -32601,
	INVALID_PARAMS = -32602,
	INTERNAL_ERROR = -32603,

	-- Custom error codes
	BUILD_NOT_FOUND = -32000,
	ITEM_PARSE_ERROR = -32001,
	CALCULATION_ERROR = -32002
}

-- Create JSON-RPC error response
function protocol.createError(id, code, message, data)
	return {
		jsonrpc = "2.0",
		id = id,
		error = {
			code = code,
			message = message,
			data = data
		}
	}
end

-- Create JSON-RPC success response
function protocol.createResponse(id, result)
	return {
		jsonrpc = "2.0",
		id = id,
		result = result
	}
end

-- Handle 'initialize' request
function protocol.handleInitialize(params)
	return {
		protocolVersion = protocol.SERVER_INFO.protocolVersion,
		capabilities = protocol.CAPABILITIES,
		serverInfo = {
			name = protocol.SERVER_INFO.name,
			version = protocol.SERVER_INFO.version
		}
	}
end

-- Handle 'tools/list' request
function protocol.handleToolsList(params)
	return {
		tools = protocol.TOOLS
	}
end

-- Handle 'tools/call' request
function protocol.handleToolsCall(params, handlers)
	local toolName = params.name
	local arguments = params.arguments or {}

	if not handlers[toolName] then
		error("Tool not found: " .. toolName)
	end

	-- Call the appropriate handler
	local success, result = pcall(handlers[toolName], arguments)

	if not success then
		error("Tool execution failed: " .. tostring(result))
	end

	return {
		content = {
			{
				type = "text",
				text = json.encode(result, { indent = true })
			}
		}
	}
end

-- Main request dispatcher
function protocol.handleRequest(request, toolHandlers)
	-- Parse JSON if it's a string
	local req
	if type(request) == "string" then
		local success, decoded = pcall(json.decode, request)
		if not success then
			return protocol.createError(nil, protocol.ERROR_CODES.PARSE_ERROR, "Parse error", decoded)
		end
		req = decoded
	else
		req = request
	end

	-- Validate JSON-RPC version
	if req.jsonrpc ~= "2.0" then
		return protocol.createError(req.id, protocol.ERROR_CODES.INVALID_REQUEST, "Invalid JSON-RPC version")
	end

	local method = req.method
	local params = req.params or {}
	local id = req.id

	-- Handle different methods
	local success, result = pcall(function()
		if method == "initialize" then
			return protocol.handleInitialize(params)
		elseif method == "tools/list" then
			return protocol.handleToolsList(params)
		elseif method == "tools/call" then
			return protocol.handleToolsCall(params, toolHandlers)
		else
			error("Method not found: " .. tostring(method))
		end
	end)

	if not success then
		local errorMsg = tostring(result)
		local errorCode = protocol.ERROR_CODES.INTERNAL_ERROR

		if errorMsg:match("Method not found") then
			errorCode = protocol.ERROR_CODES.METHOD_NOT_FOUND
		elseif errorMsg:match("Tool not found") then
			errorCode = protocol.ERROR_CODES.METHOD_NOT_FOUND
		elseif errorMsg:match("BUILD_NOT_FOUND") then
			errorCode = protocol.ERROR_CODES.BUILD_NOT_FOUND
		elseif errorMsg:match("ITEM_PARSE_ERROR") then
			errorCode = protocol.ERROR_CODES.ITEM_PARSE_ERROR
		elseif errorMsg:match("CALCULATION_ERROR") then
			errorCode = protocol.ERROR_CODES.CALCULATION_ERROR
		end

		return protocol.createError(id, errorCode, errorMsg)
	end

	return protocol.createResponse(id, result)
end

return protocol

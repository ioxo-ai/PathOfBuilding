#!/bin/bash
# MCP Server Launcher
# Ensures correct working directory for PathOfBuilding MCP server

cd "$(dirname "$0")/src" || exit 1
exec luajit HeadlessWrapper.lua "$@"

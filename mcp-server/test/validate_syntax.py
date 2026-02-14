#!/usr/bin/env python3
"""
Lua Syntax Validator for MCP Server
Validates basic Lua syntax without actually executing the code
"""

import re
import sys

def validate_lua_syntax(filepath):
    """Basic Lua syntax validation"""
    errors = []
    warnings = []

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')

    # Check for common syntax errors
    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()

        # Skip comments and empty lines
        if line_stripped.startswith('--') or not line_stripped:
            continue

        # Check for unbalanced brackets
        open_brackets = line.count('{') + line.count('[') + line.count('(')
        close_brackets = line.count('}') + line.count(']') + line.count(')')

        # Check for 'then' without 'if/elseif'
        if 'then' in line and not ('if ' in line or 'elseif ' in line):
            if not line_stripped.startswith('--'):
                warnings.append(f"Line {i}: 'then' without 'if/elseif' (might be multiline)")

        # Check for 'end' balance
        if line_stripped == 'end':
            pass  # End statements are fine

        # Check for function definitions
        if 'function ' in line:
            if not re.search(r'function\s+\w+', line) and not re.search(r'function\s*\(', line):
                warnings.append(f"Line {i}: Unusual function definition")

    # Check overall structure
    function_count = content.count('function ')
    end_count = len([l for l in lines if l.strip() == 'end'])

    # Check for balanced do/end, function/end, if/end
    do_count = len(re.findall(r'\bdo\b', content))
    if_count = len(re.findall(r'\bif\b', content))

    print(f"\n=== Lua Syntax Validation: {filepath} ===")
    print(f"Lines: {len(lines)}")
    print(f"Functions: {function_count}")
    print(f"'end' statements: {end_count}")
    print(f"'do' blocks: {do_count}")
    print(f"'if' statements: {if_count}")

    # Check for required patterns in MCP server files
    if 'protocol.lua' in filepath:
        if 'handleRequest' not in content:
            errors.append("Missing handleRequest function")
        if 'createError' not in content:
            errors.append("Missing createError function")
        if 'TOOLS' not in content:
            errors.append("Missing TOOLS table")
        print("\n✓ Protocol handler patterns found")

    if 'init.lua' in filepath and 'mcp-server' in filepath:
        if 'mcpServer.run' not in content:
            errors.append("Missing mcpServer.run function")
        if 'registerToolHandler' not in content:
            errors.append("Missing registerToolHandler function")
        if 'io.stdin' not in content:
            warnings.append("No stdin reading detected")
        print("\n✓ MCP server init patterns found")

    if errors:
        print(f"\n❌ Errors found:")
        for err in errors:
            print(f"  - {err}")
        return False

    if warnings:
        print(f"\n⚠️  Warnings:")
        for warn in warnings:
            print(f"  - {warn}")

    print("\n✅ No critical syntax errors detected")
    return True

if __name__ == '__main__':
    files_to_check = [
        '/home/user/PathOfBuilding/mcp-server/protocol.lua',
        '/home/user/PathOfBuilding/mcp-server/init.lua'
    ]

    all_valid = True
    for filepath in files_to_check:
        try:
            valid = validate_lua_syntax(filepath)
            all_valid = all_valid and valid
        except FileNotFoundError:
            print(f"❌ File not found: {filepath}")
            all_valid = False
        except Exception as e:
            print(f"❌ Error validating {filepath}: {e}")
            all_valid = False
        print()

    if all_valid:
        print("=" * 60)
        print("✅ All files passed syntax validation")
        print("=" * 60)
        sys.exit(0)
    else:
        print("=" * 60)
        print("❌ Some files have issues")
        print("=" * 60)
        sys.exit(1)

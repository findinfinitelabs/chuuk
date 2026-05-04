#!/usr/bin/env python3
"""
Stdio entry-point for the Chuuk Dictionary MCP server.

Usage (add to your MCP client config):
  {
    "mcpServers": {
      "chuuk-dictionary": {
        "command": "python",
        "args": ["-m", "mcp_server.run_stdio"],
        "env": { "APP_BASE_URL": "http://localhost:5000" }
      }
    }
  }
"""

import asyncio
import sys
import os

# Ensure the project root is on the path when run as a module
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mcp_server.server import build_mcp_server  # noqa: E402


async def main() -> None:
    import mcp.server.stdio  # type: ignore

    server = build_mcp_server()
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())

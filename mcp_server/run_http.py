#!/usr/bin/env python3
"""
Thin HTTP wrapper for the Chuuk Dictionary MCP tools.
Exposes the same five tools as a JSON-over-HTTP API on port 8001
(configurable via MCP_HTTP_PORT env var).

POST /tools/<name>   — call tool by name with JSON body
GET  /tools          — list available tools
GET  /health         — health check

Usage:
  python -m mcp_server.run_http
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, jsonify, request  # noqa: E402
from mcp_server.server import TOOL_DISPATCH, TOOLS  # noqa: E402

http_app = Flask("chuuk-mcp-http")
MCP_HTTP_PORT = int(os.getenv("MCP_HTTP_PORT", "8001"))


@http_app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "chuuk-dictionary-mcp"})


@http_app.route("/tools", methods=["GET"])
def list_tools():
    return jsonify({"tools": TOOLS})


@http_app.route("/tools/<name>", methods=["POST"])
def call_tool(name: str):
    handler = TOOL_DISPATCH.get(name)
    if not handler:
        return jsonify({"error": f"Unknown tool: {name}"}), 404
    args = request.get_json(silent=True) or {}
    try:
        result = handler(args)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(result)


if __name__ == "__main__":
    print(f"🌐 Starting Chuuk Dictionary MCP HTTP server on :{MCP_HTTP_PORT}")
    http_app.run(host="0.0.0.0", port=MCP_HTTP_PORT, debug=False)

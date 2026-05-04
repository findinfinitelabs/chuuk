#!/usr/bin/env python3
"""
Chuuk Dictionary MCP Server
============================
Exposes Helsinki translation and training tools via the Model Context Protocol
(stdio transport).  An HTTP wrapper lives in http_wrapper.py.

Tools exposed:
  - translate          Translate text CHK↔EN using the Helsinki stack
  - fix_translation    Submit a correction pair and optionally run LoRA teach
  - start_training     Trigger a full fine-tune run
  - get_training_status  Return current training engine status
  - teach_pair         Quick LoRA pair teach (fires and returns immediately)

Run:  python -m mcp_server.run_stdio
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Attempt to import the MCP SDK.  If it is not installed the server will
# fail at startup with a clear error message rather than silently at import.
# ---------------------------------------------------------------------------
try:
    import mcp.server.stdio  # type: ignore
    from mcp.server import Server  # type: ignore
    from mcp.types import TextContent, Tool  # type: ignore
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

# ---------------------------------------------------------------------------
# Internal helper — call the Flask app directly rather than over HTTP so
# that the MCP server can be embedded in the same process OR run standalone.
# ---------------------------------------------------------------------------

def _flask_post(path: str, payload: dict) -> dict:
    """
    Call a Flask route directly using the test client when running in-process,
    otherwise fall back to HTTP against APP_BASE_URL.
    """
    base_url = os.getenv("APP_BASE_URL", "http://localhost:5000")
    import requests as _requests  # noqa: PLC0415
    try:
        resp = _requests.post(f"{base_url}{path}", json=payload, timeout=300)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def _flask_get(path: str) -> dict:
    base_url = os.getenv("APP_BASE_URL", "http://localhost:5000")
    import requests as _requests  # noqa: PLC0415
    try:
        resp = _requests.get(f"{base_url}{path}", timeout=30)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool implementations (thin wrappers around the Flask API)
# ---------------------------------------------------------------------------

def tool_translate(text: str, direction: str = "auto") -> dict:
    """Translate text between Chuukese and English."""
    return _flask_post("/api/translate", {"text": text, "direction": direction})


def tool_fix_translation(
    original_text: str,
    corrected_text: str,
    direction: str = "auto",
    teach_lora: bool = True,
) -> dict:
    """Submit a translation correction.  If teach_lora=True, runs LoRA teach immediately."""
    result = _flask_post("/api/translate/correction", {
        "original_text": original_text,
        "corrected_text": corrected_text,
        "direction": direction,
        "retrain": False,
    })
    if teach_lora and result.get("success"):
        # Determine pair direction
        if direction == "chk_to_en":
            chk, eng = original_text, corrected_text
        elif direction == "en_to_chk":
            chk, eng = corrected_text, original_text
        else:
            # auto — assume English input if ASCII
            if all(ord(c) < 128 for c in original_text if c.isalpha()):
                chk, eng = corrected_text, original_text
            else:
                chk, eng = original_text, corrected_text

        lora_result = _flask_post("/api/ai-training/lora-teach", {
            "chuukese": chk,
            "english": eng,
            "direction": direction,
        })
        result["lora_teach"] = lora_result
    return result


def tool_start_training(num_epochs: int = 3, batch_size: int = 2) -> dict:
    """Start a full fine-tune of both Helsinki models."""
    return _flask_post("/api/ai-training/start", {
        "num_epochs": num_epochs,
        "batch_size": batch_size,
    })


def tool_get_training_status() -> dict:
    """Get current training engine status."""
    return _flask_get("/api/ai-training/status")


def tool_teach_pair(chuukese: str, english: str, direction: str = "both") -> dict:
    """Immediately apply a LoRA adapter update to teach one pair."""
    return _flask_post("/api/ai-training/lora-teach", {
        "chuukese": chuukese,
        "english": english,
        "direction": direction,
    })


# ---------------------------------------------------------------------------
# MCP Server definition
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "name": "translate",
        "description": "Translate text between Chuukese (CHK) and English using Helsinki-NLP models.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to translate."},
                "direction": {
                    "type": "string",
                    "enum": ["auto", "chk_to_en", "en_to_chk"],
                    "default": "auto",
                    "description": "Translation direction. 'auto' detects from script.",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "fix_translation",
        "description": "Submit a corrected translation pair and optionally teach it to the model via LoRA.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "original_text": {"type": "string"},
                "corrected_text": {"type": "string"},
                "direction": {
                    "type": "string",
                    "enum": ["auto", "chk_to_en", "en_to_chk"],
                    "default": "auto",
                },
                "teach_lora": {
                    "type": "boolean",
                    "default": True,
                    "description": "If true, immediately apply a LoRA update to learn this correction.",
                },
            },
            "required": ["original_text", "corrected_text"],
        },
    },
    {
        "name": "start_training",
        "description": "Start a full fine-tune of both Helsinki CHK↔EN models.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "num_epochs": {"type": "integer", "default": 3},
                "batch_size": {"type": "integer", "default": 2},
            },
        },
    },
    {
        "name": "get_training_status",
        "description": "Get current training engine status, recent runs, and data source counts.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "teach_pair",
        "description": "Immediately teach the Helsinki model one Chuukese↔English pair via LoRA.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chuukese": {"type": "string"},
                "english": {"type": "string"},
                "direction": {
                    "type": "string",
                    "enum": ["both", "chk_to_en", "en_to_chk"],
                    "default": "both",
                },
            },
            "required": ["chuukese", "english"],
        },
    },
]

TOOL_DISPATCH = {
    "translate": lambda args: tool_translate(**args),
    "fix_translation": lambda args: tool_fix_translation(**args),
    "start_training": lambda args: tool_start_training(**args),
    "get_training_status": lambda _args: tool_get_training_status(),
    "teach_pair": lambda args: tool_teach_pair(**args),
}


def build_mcp_server() -> "Server":
    """Build and return a configured MCP Server instance."""
    if not MCP_AVAILABLE:
        raise ImportError("mcp package not installed — run: pip install mcp>=1.0.0")

    server = Server("chuuk-dictionary")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in TOOLS
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        handler = TOOL_DISPATCH.get(name)
        if not handler:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
        try:
            result = handler(arguments)
        except Exception as e:
            result = {"error": str(e)}
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    return server

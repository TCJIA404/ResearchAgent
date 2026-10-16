"""Synchronous, allow-listed MCP stdio bridge for LangGraph Executor.

The MCP SDK client opens a fresh local server for each planned analysis step.
No arbitrary model-written Python or shell commands are executed. The server
itself delegates to the Day 2 restricted CSV analyzer.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent
SERVER = ROOT / "mcp_server.py"
ALLOWED_DATASET = "demo_gasification"
ALLOWED_OPERATIONS = {"summary", "correlation", "scatter_plot"}
ALLOWED_COLUMNS = {
    "temperature_C", "steam_fuel_ratio", "hydrogen_vol_pct",
    "total_syngas_yield_Nm3_per_kg",
}


def _extract_analysis(value: Any, operation: str) -> Dict[str, Any]:
    """Find the expected structured result, not arbitrary MCP metadata."""
    if isinstance(value, dict):
        if (value.get("status") in ("OK", "ERROR") and
                value.get("operation") == operation):
            return value
        for nested in value.values():
            try:
                return _extract_analysis(nested, operation)
            except ValueError:
                pass
    if isinstance(value, list):
        for nested in value:
            try:
                return _extract_analysis(nested, operation)
            except ValueError:
                pass
    raise ValueError("MCP response contained no matching structured analysis")


async def _call_mcp(operation: str, x: str, y: str) -> Dict[str, Any]:
    from mcp import Client, StdioServerParameters

    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    async with Client(params) as client:
        listing = await client.list_tools()
        if "analyze_demo_csv" not in {tool.name for tool in listing.tools}:
            raise RuntimeError("Approved MCP analysis tool not discoverable")
        result = await client.call_tool(
            "analyze_demo_csv", {"operation": operation, "x": x, "y": y})
        if result.is_error:
            raise RuntimeError("MCP server returned a tool error")
        payload = getattr(result, "structured_content", None)
        if payload is None:
            content = getattr(result, "content", None) or []
            if not content or not hasattr(content[0], "text"):
                raise ValueError("MCP tool returned no JSON content")
            payload = json.loads(content[0].text)
        analysis = _extract_analysis(payload, operation)
        if analysis.get("status") != "OK":
            raise ValueError("MCP analysis reported a failure")
        if analysis.get("dataset") != ALLOWED_DATASET:
            raise ValueError("MCP returned an unexpected dataset")
        if "SYNTHETIC" not in str(analysis.get("provenance_warning", "")):
            raise ValueError("MCP result is missing synthetic provenance")
        if operation == "scatter_plot":
            chart = analysis.get("chart_path")
            permitted = (ROOT / "outputs" / "charts").resolve()
            if not isinstance(chart, str) or not Path(chart).resolve().is_relative_to(permitted):
                raise ValueError("MCP chart escaped the controlled output directory")
            if not Path(chart).is_file():
                raise ValueError("MCP chart file does not exist")
        analysis["mcp_tool"] = "analyze_demo_csv"
        analysis["transport"] = "stdio"
        return analysis


def analyze_csv_via_mcp(dataset: str, operation: str,
                        x: str = "", y: str = "") -> Dict[str, Any]:
    """LangGraph synchronous adapter. Validate before spawning any subprocess."""
    if dataset != ALLOWED_DATASET or operation not in ALLOWED_OPERATIONS:
        raise ValueError("MCP dataset or operation not allowed")
    if operation == "summary":
        if x or y:
            raise ValueError("MCP summary cannot include x/y columns")
        x, y = "temperature_C", "hydrogen_vol_pct"  # server defaults, ignored for summary
    elif x not in ALLOWED_COLUMNS or y not in ALLOWED_COLUMNS or x == y:
        raise ValueError("MCP columns must be distinct and from the allow-list")
    if not SERVER.is_file():
        raise FileNotFoundError("MCP server file not found")
    return asyncio.run(_call_mcp(operation, x, y))

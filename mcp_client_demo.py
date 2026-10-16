"""Discover and call local MCP v2 tools; no LLM or RAG API required."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters


def _find_field(value, field):
    if isinstance(value, dict):
        if field in value:
            return value[field]
        for child in value.values():
            found = _find_field(child, field)
            if found is not None:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_field(child, field)
            if found is not None:
                return found
    return None


def _decode_result(result):
    if result.is_error:
        raise RuntimeError("MCP tool returned an error: " + str(result.content))
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return structured
    if result.content:
        return json.loads(result.content[0].text)
    raise RuntimeError("MCP tool returned no content")


async def run_demo():
    root = Path(__file__).resolve().parent
    params = StdioServerParameters(command=sys.executable, args=[str(root / "mcp_server.py")])
    async with Client(params) as client:
        listing = await client.list_tools()
        names = {tool.name for tool in listing.tools}
        assert {"list_datasets", "describe_dataset", "analyze_demo_csv"} <= names, names
        print("[PASS] MCP server discovery:", ", ".join(sorted(names)))

        data = _decode_result(await client.call_tool("list_datasets", {}))
        assert _find_field(data, "available") is True, data
        assert "SYNTHETIC" in str(_find_field(data, "provenance")), data
        print("[PASS] Synthetic dataset discovery with provenance")
        detail = _decode_result(await client.call_tool("describe_dataset", {"dataset": "demo_gasification"}))
        assert _find_field(detail, "rows") == 16, detail
        assert "temperature_C" in _find_field(detail, "columns"), detail
        print("[PASS] Approved CSV metadata: 16 rows with declared columns")

        args = {"operation": "correlation", "x": "temperature_C", "y": "hydrogen_vol_pct"}
        computed = _decode_result(await client.call_tool("analyze_demo_csv", args))
        r = _find_field(computed, "pearson_r")
        assert r is not None and abs(float(r) - 0.8755451036924878) < 0.0001, computed
        print(f"[PASS] MCP correlation tool: Pearson r={float(r):.6f} (SYNTHETIC ONLY)")

        args["operation"] = "scatter_plot"
        chart = _decode_result(await client.call_tool("analyze_demo_csv", args))
        chart_path = _find_field(chart, "chart_path")
        assert isinstance(chart_path, str) and Path(chart_path).is_file(), chart
        print("[PASS] MCP scatter tool produced PNG:", chart_path)
    print("All Day 3 MCP tool discovery/call tests passed. Agent integration is a separate step.")


if __name__ == "__main__":
    asyncio.run(run_demo())

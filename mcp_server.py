"""Local, constrained MCP tools backed by the already-tested Day 2 CLI.

Compatible with the official MCP Python SDK v2 (not the legacy v1 FastMCP API).
Never print to stdout before/while serving over stdio.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Literal

from mcp.server import MCPServer

BASE_DIR = Path(__file__).resolve().parent
ANALYZER = BASE_DIR / "data_analysis_tool.py"
DATA_FILE = BASE_DIR / "data" / "demo_gasification.csv"
ALLOWED_COLUMNS = (
    "temperature_C",
    "steam_fuel_ratio",
    "hydrogen_vol_pct",
    "total_syngas_yield_Nm3_per_kg",
)

mcp = MCPServer("ResearchAgent Safe CSV Tools")


@mcp.tool()
def list_datasets() -> dict:
    """List allow-listed demonstration datasets and their columns, with provenance warnings."""
    return {
        "status": "OK" if DATA_FILE.is_file() else "MISSING_DATASET",
        "datasets": [
            {
                "name": "demo_gasification",
                "columns": list(ALLOWED_COLUMNS),
                "available": DATA_FILE.is_file(),
                "provenance": "SYNTHETIC DEMONSTRATION DATA; not experimental evidence or a scientific finding",
            }
        ],
    }


@mcp.tool()
def describe_dataset(dataset: Literal["demo_gasification"] = "demo_gasification") -> dict:
    """Return the approved synthetic CSV schema and row count; no raw records are exposed."""
    if dataset != "demo_gasification" or not DATA_FILE.is_file():
        return {"status": "ERROR", "message": "Dataset is not allow-listed or not available"}
    try:
        with DATA_FILE.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            columns = next(reader)
            count = sum(1 for _ in reader)
    except (OSError, UnicodeError, csv.Error, StopIteration):
        return {"status": "ERROR", "message": "Could not read approved dataset metadata"}
    if columns != list(ALLOWED_COLUMNS):
        return {"status": "ERROR", "message": "Demo dataset schema does not match its allow-list"}
    return {
        "status": "OK",
        "dataset": dataset,
        "rows": count,
        "columns": columns,
        "provenance_warning": "SYNTHETIC DEMONSTRATION DATA; not experimental evidence or a scientific finding",
    }


@mcp.tool()
def analyze_demo_csv(
    operation: Literal["summary", "correlation", "scatter_plot"],
    x: Literal[
        "temperature_C", "steam_fuel_ratio", "hydrogen_vol_pct", "total_syngas_yield_Nm3_per_kg"
    ] = "temperature_C",
    y: Literal[
        "temperature_C", "steam_fuel_ratio", "hydrogen_vol_pct", "total_syngas_yield_Nm3_per_kg"
    ] = "hydrogen_vol_pct",
) -> dict:
    """Safely analyze the synthetic demo_gasification CSV using the existing Day 2 validator."""
    if not ANALYZER.is_file() or not DATA_FILE.is_file():
        return {"status": "ERROR", "message": "Day 2 analyzer or demo CSV is missing"}
    if operation != "summary" and x == y:
        return {"status": "ERROR", "message": "x and y must be different"}
    args = [sys.executable, str(ANALYZER), "--dataset", "demo_gasification", "--operation", operation]
    if operation != "summary":
        args.extend(["--x", x, "--y", y])
    if operation == "scatter_plot":
        args.append("--save")
    try:
        completed = subprocess.run(
            args, cwd=str(BASE_DIR), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60, check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "ERROR", "message": "The restricted analyzer timed out"}
    except OSError as exc:
        return {"status": "ERROR", "message": f"The restricted analyzer could not start: {type(exc).__name__}"}
    if completed.returncode != 0:
        return {"status": "ERROR", "message": "Analysis command failed", "details": completed.stderr[-500:]}
    try:
        output, _ = json.JSONDecoder().raw_decode(completed.stdout.lstrip())
    except (ValueError, TypeError):
        return {"status": "ERROR", "message": "Analysis command returned non-JSON output"}
    if not isinstance(output, dict):
        return {"status": "ERROR", "message": "Analysis output must be a JSON object"}
    output.setdefault("provenance_warning", "SYNTHETIC DEMONSTRATION DATA; not experimental evidence")
    output["mcp_tool"] = "analyze_demo_csv"
    return output


if __name__ == "__main__":
    mcp.run()  # stdio; a client launches this subprocess.

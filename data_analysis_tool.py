"""Day 2: safe, deterministic CSV analysis for ResearchAgent.

No eval/exec, arbitrary Python execution, remote downloads, or arbitrary paths.
Only CSV files inside the local data/ folder are accepted. Reports and charts
are not evidence of causality; always distinguish demo data from research data.

Example:
  python data_analysis_tool.py --dataset demo_gasification --operation summary
  python data_analysis_tool.py --dataset demo_gasification --operation correlation --x temperature_C --y hydrogen_vol_pct
  python data_analysis_tool.py --dataset demo_gasification --operation scatter_plot --x temperature_C --y hydrogen_vol_pct
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"
MAX_CSV_BYTES = 5_000_000
MAX_ROWS = 10_000
MAX_COLUMNS = 60
DATASET_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
OPERATIONS = {"summary", "correlation", "scatter_plot"}


class DatasetError(ValueError):
    """Invalid dataset, invalid operation, or insufficient numerical data."""


def _load_csv(dataset: str, data_dir: Path) -> tuple[pd.DataFrame, Path]:
    if not isinstance(dataset, str) or not DATASET_RE.fullmatch(dataset):
        raise DatasetError("Dataset must be an ID such as demo_gasification, not a path")
    data_root = data_dir.resolve()
    path = (data_root / (dataset + ".csv")).resolve()
    if path.parent != data_root or not path.is_file():
        raise DatasetError("Dataset CSV does not exist inside data/")
    if path.stat().st_size > MAX_CSV_BYTES:
        raise DatasetError("CSV exceeds the 5 MB limit")
    try:
        frame = pd.read_csv(path, encoding="utf-8-sig", nrows=MAX_ROWS + 1)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeError, OSError) as exc:
        raise DatasetError("Cannot read CSV ({})".format(type(exc).__name__)) from exc
    if frame.empty or len(frame) > MAX_ROWS or len(frame.columns) > MAX_COLUMNS:
        raise DatasetError("CSV must have 1-10000 data rows and at most 60 columns")
    if frame.columns.has_duplicates:
        raise DatasetError("CSV has duplicate column names")
    # Default pandas inference can rename duplicate headings (e.g. H2, H2.1).
    # Verify raw first-line headers separately to avoid ambiguous column selection.
    import csv
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fp:
            raw_headers = next(csv.reader(fp))
    except (OSError, UnicodeError, StopIteration) as exc:
        raise DatasetError("Invalid CSV header") from exc
    if len(set(raw_headers)) != len(raw_headers) or any(not h.strip() for h in raw_headers):
        raise DatasetError("CSV requires non-empty, unique column headers")
    return frame, path


def _numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise DatasetError("Unknown column: {}".format(column))
    original = frame[column]
    values = pd.to_numeric(original, errors="coerce").replace([float("inf"), float("-inf")], float("nan"))
    if not values.notna().any():
        raise DatasetError("Column has no numeric values: {}".format(column))
    # Converting invalid or blank cells to missing is explicitly reported in output.
    return values


def _clean_number(value: Any) -> int | float | None:
    if pd.isna(value):
        return None
    val = float(value)
    return val if math.isfinite(val) else None


def _data_note(dataset: str) -> str:
    if dataset == "demo_gasification":
        return "SYNTHETIC DEMONSTRATION DATA; not experimental evidence or a scientific finding"
    return "Local user-provided CSV; provenance and measurement quality have not been verified"


def analyze_csv(
    dataset: str,
    operation: str,
    x: str | None = None,
    y: str | None = None,
    *,
    data_dir: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Run allowlisted analysis on one safely identified local CSV.

    Returns JSON-serializable results for later use as an Agent tool.
    This function never executes model-generated Python code.
    """
    if operation not in OPERATIONS:
        raise DatasetError("Allowed operations: summary, correlation, scatter_plot")
    frame, path = _load_csv(dataset, data_dir or DATA_DIR)
    result: dict[str, Any] = {
        "status": "OK",
        "dataset": dataset,
        "file": path.name,
        "operation": operation,
        "rows": int(len(frame)),
        "columns": [str(c) for c in frame.columns],
        "provenance_warning": _data_note(dataset),
    }
    if operation == "summary":
        summaries: dict[str, Any] = {}
        for column in frame.columns:
            values = pd.to_numeric(frame[column], errors="coerce").replace(
                [float("inf"), float("-inf")], float("nan")
            )
            if not values.notna().any():
                continue
            valid = values.dropna()
            summaries[column] = {
                "valid_count": int(valid.size),
                "missing_or_invalid_count": int(len(frame) - len(valid)),
                "mean": _clean_number(valid.mean()),
                "std_sample": _clean_number(valid.std(ddof=1)),
                "min": _clean_number(valid.min()),
                "max": _clean_number(valid.max()),
            }
        if not summaries:
            raise DatasetError("No numeric columns available for summary")
        result["statistics"] = summaries
        return result

    if not x or not y or x == y:
        raise DatasetError("Correlation/scatter requires two different columns: --x and --y")
    vx, vy = _numeric_series(frame, x), _numeric_series(frame, y)
    pair = pd.DataFrame({"x": vx, "y": vy}).dropna()
    if len(pair) < 3:
        raise DatasetError("At least three complete numeric pairs are required")
    if pair["x"].nunique() < 2 or pair["y"].nunique() < 2:
        raise DatasetError("Cannot correlate or plot constant-valued columns")
    result.update({
        "x": x,
        "y": y,
        "paired_rows": int(len(pair)),
        "excluded_rows": int(len(frame) - len(pair)),
        "pearson_r": _clean_number(pair["x"].corr(pair["y"])),
        "interpretation_warning": "Pearson correlation alone cannot establish causation",
    })
    if operation == "correlation":
        return result

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = (output_dir or OUTPUT_DIR).resolve() / "charts"
    out.mkdir(parents=True, exist_ok=True)
    safe_hash = hashlib.sha256((dataset + ":" + x + ":" + y).encode("utf-8")).hexdigest()[:12]
    chart = out / (dataset + "_scatter_" + safe_hash + ".png")
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    try:
        ax.scatter(pair["x"].values, pair["y"].values, alpha=0.85)
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        ax.set_title("Exploratory scatter: " + dataset)
        ax.grid(True, alpha=0.25)
        fig.tight_layout()
        fig.savefig(chart, dpi=160)
    finally:
        plt.close(fig)
    result["chart_path"] = str(chart)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Restricted ResearchAgent CSV analysis tool")
    parser.add_argument("--dataset", required=True, help="CSV ID inside data/; omit .csv")
    parser.add_argument("--operation", required=True, choices=sorted(OPERATIONS))
    parser.add_argument("--x", help="X column (for correlation/scatter_plot)")
    parser.add_argument("--y", help="Y column (for correlation/scatter_plot)")
    parser.add_argument("--save", action="store_true", help="Save JSON under local outputs/")
    args = parser.parse_args()
    try:
        result = analyze_csv(args.dataset, args.operation, args.x, args.y)
    except (DatasetError, OSError) as exc:
        parser.exit(1, "ANALYSIS FAILED: {}\n".format(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.save:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        target = OUTPUT_DIR / ("analysis_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".json")
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Saved locally: " + str(target))


if __name__ == "__main__":
    main()

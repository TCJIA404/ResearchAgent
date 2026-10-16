"""Offline tests; no LLM calls or FastAPI service required."""
import json
import tempfile
from pathlib import Path

from data_analysis_tool import DatasetError, analyze_csv


def must_reject(func, clue):
    try:
        func()
    except DatasetError:
        return
    raise AssertionError("Unsafe/invalid input unexpectedly accepted: " + clue)


def main():
    basic = analyze_csv("demo_gasification", "summary")
    assert basic["status"] == "OK" and basic["rows"] == 16
    assert basic["statistics"]["hydrogen_vol_pct"]["valid_count"] == 16
    assert "SYNTHETIC" in basic["provenance_warning"]
    json.dumps(basic)
    print("[PASS] Summary: row counts, missing values and statistics")

    corr = analyze_csv("demo_gasification", "correlation", "temperature_C", "hydrogen_vol_pct")
    assert corr["paired_rows"] == 16
    assert 0 < corr["pearson_r"] < 1
    assert "causation" in corr["interpretation_warning"]
    print("[PASS] Pearson correlation: paired rows, finite result, no causality claim")

    with tempfile.TemporaryDirectory() as tmp:
        out = analyze_csv("demo_gasification", "scatter_plot", "temperature_C", "hydrogen_vol_pct", output_dir=Path(tmp))
        chart = Path(out["chart_path"])
        assert chart.is_file() and chart.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        print("[PASS] Scatter plot created as a real PNG in a controlled output folder")

    must_reject(lambda: analyze_csv("../.env.agent", "summary"), "path traversal")
    must_reject(lambda: analyze_csv("demo_gasification", "exec"), "arbitrary operation")
    must_reject(lambda: analyze_csv("demo_gasification", "correlation", "temp", "hydrogen_vol_pct"), "unknown column")
    must_reject(lambda: analyze_csv("demo_gasification", "correlation", "temperature_C", "temperature_C"), "same column")
    print("[PASS] Unsupported operations, traversal and invalid columns rejected")

    with tempfile.TemporaryDirectory() as tmp:
        data_root = Path(tmp)
        (data_root / "empty_numeric.csv").write_text("a,b\nfoo,bar\nbaz,qux\n", encoding="utf-8")
        must_reject(lambda: analyze_csv("empty_numeric", "summary", data_dir=data_root), "nonnumeric")
        (data_root / "bad_pairs.csv").write_text("x,y\n1,3\n2,\n,4\n", encoding="utf-8")
        must_reject(lambda: analyze_csv("bad_pairs", "correlation", "x", "y", data_dir=data_root), "too few pairs")
        (data_root / "duplicate.csv").write_text("x,x\n1,2\n3,4\n", encoding="utf-8")
        must_reject(lambda: analyze_csv("duplicate", "summary", data_dir=data_root), "duplicate headers")
    print("[PASS] Nonnumeric, incomplete and duplicated-column datasets rejected")

    print("All Day 2 CSV analysis offline tests passed.")


if __name__ == "__main__":
    main()

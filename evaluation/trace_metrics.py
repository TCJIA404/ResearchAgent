"""Audit saved ResearchAgent traces; no LLM/API calls and no PDF content exported.

Usage:
    python -m evaluation.trace_metrics --input outputs --output-dir eval_outputs
    python -m evaluation.trace_metrics --input "D:\\old-backup\\outputs" --output-dir eval_outputs

This measures observed workflow/trace indicators, NOT independently validated
scientific correctness, ground-truth task success, or wall-clock performance.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List

REF_RE = re.compile(r"\(([^\s(),]+\.pdf),\s*p\.(\d+)\)", re.IGNORECASE)
GOOD_REPORT_STATES = {"SOURCES_LINKED_NOT_FACT_CHECKED", "PARTIAL_ANALYSIS_FAILED_NOT_FACT_CHECKED"}
ANALYSIS_ACTIONS = {"analyze_csv", "mcp_analyze_csv"}
TOOL_ACTIONS = {"search_papers", "ask_rag", "analyze_csv", "mcp_analyze_csv"}


def refs_in(text: str) -> set[str]:
    if not isinstance(text, str):
        return set()
    return {f"({source}, p.{int(page)})" for source, page in REF_RE.findall(text) if int(page) > 0}


def _is_synthetic(record: Dict[str, Any]) -> bool:
    analysis = record.get("analysis_result")
    return isinstance(analysis, dict) and "SYNTHETIC" in str(analysis.get("provenance_warning", "")).upper()


TIMING_NODES = ("planner_ms", "executor_ms", "verifier_ms", "writer_ms")


def _valid_timings(raw: Any) -> Dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    result = {}
    for key in TIMING_NODES:
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if math.isfinite(value) and value >= 0:
                result[key] = round(float(value), 3)
    return result


def assess_trace(name: str, trace: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(trace, dict) or not isinstance(trace.get("plan"), dict):
        raise ValueError("Missing top-level plan object")
    steps = trace["plan"].get("steps")
    records = trace.get("records")
    if not isinstance(steps, list) or not isinstance(records, list):
        raise ValueError("Missing plan.steps or records list")
    if not all(isinstance(s, dict) for s in steps) or not all(isinstance(r, dict) for r in records):
        raise ValueError("Plan/records entries must be objects")

    expected = [s.get("action") for s in steps if s.get("action") != "final_answer"]
    actual = [r.get("action") for r in records]
    if any(a not in TOOL_ACTIONS for a in expected + actual):
        raise ValueError("Unknown tool action")
    executed_all = len(actual) == len(expected) and actual == expected
    tool_errors = sum(r.get("status") == "TOOL_ERROR" for r in records)
    successful_calls = sum(r.get("status") in {"EVIDENCE_FOUND", "NO_EVIDENCE", "SUPPLEMENT_ONLY", "ANALYSIS_OK"}
                           for r in records)
    search_steps = [r for r in records if r.get("action") == "search_papers"]
    found_searches = sum(r.get("status") == "EVIDENCE_FOUND" for r in search_steps)
    analysis_steps = [r for r in records if r.get("action") in ANALYSIS_ACTIONS]
    synthetic = any(_is_synthetic(r) for r in analysis_steps)
    answer = trace.get("answer", "")
    answer = answer if isinstance(answer, str) else ""
    recorded_refs = set(trace.get("refs", [])) if isinstance(trace.get("refs"), list) else set()
    cited_refs = refs_in(answer)
    matched_refs = cited_refs & recorded_refs
    unknown_refs = cited_refs - recorded_refs
    status = trace.get("status", "UNKNOWN")
    report_completed = bool(answer.strip()) and executed_all and status in GOOD_REPORT_STATES
    report_citations = bool(cited_refs) and not unknown_refs
    synthetic_labeled = (not synthetic or any(term in answer for term in
                         ("模拟数据", "合成数据", "合成演示", "SYNTHETIC")))
    tool_status_counts = dict(sorted(Counter(str(r.get("status", "UNKNOWN")) for r in records).items()))
    timings = _valid_timings(trace.get("timings_ms"))
    per_tool_latencies = [
        {"id": r.get("id"), "action": r.get("action"), "latency_ms": round(float(r["latency_ms"]), 3)}
        for r in records
        if isinstance(r.get("latency_ms"), (int, float))
        and not isinstance(r.get("latency_ms"), bool)
        and math.isfinite(r["latency_ms"]) and r["latency_ms"] >= 0
    ]
    return {
        "file": Path(name).name,
        "status": status,
        "planned_tool_steps": len(expected),
        "executed_tool_steps": len(records),
        "step_sequence_complete": executed_all,
        "tool_calls_without_error": successful_calls,
        "tool_errors": tool_errors,
        "search_calls": len(search_steps),
        "searches_with_evidence": found_searches,
        "analysis_calls": len(analysis_steps),
        "analysis_successes": sum(r.get("status") == "ANALYSIS_OK" for r in analysis_steps),
        "final_report_completed": report_completed,
        "answer_citation_pages": len(cited_refs),
        "answer_citation_pages_matched": len(matched_refs),
        "answer_unknown_citations": sorted(unknown_refs),
        "answer_citations_all_linked": report_citations,
        "saved_search_source_pages": len(recorded_refs),
        "synthetic_analysis_used": synthetic,
        "synthetic_data_labeled": synthetic_labeled,
        "issues_count": len(trace.get("issues", [])) if isinstance(trace.get("issues"), list) else None,
        "status_counts": tool_status_counts,
        "node_timings_available": bool(timings),
        "node_timings_ms": timings or None,
        "tool_latencies_ms": per_tool_latencies or None,
        "human_fact_review": "NOT_EVALUATED",
    }


def summarize(details: List[Dict[str, Any]]) -> Dict[str, Any]:
    count = len(details)
    sums = lambda key: sum(int(r[key]) for r in details)
    total_calls = sums("executed_tool_steps")
    nonerror = sums("tool_calls_without_error")
    total_search = sums("search_calls")
    total_citations = sums("answer_citation_pages")
    synthetic = [r for r in details if r["synthetic_analysis_used"]]
    timed = [r for r in details if r["node_timings_available"]]
    node_latency = {}
    for node in TIMING_NODES:
        values = [r["node_timings_ms"][node] for r in timed
                  if node in r["node_timings_ms"]]
        if values:
            node_latency[node] = {
                "sample_count": len(values),
                "mean_ms": round(sum(values) / len(values), 3),
                "min_ms": round(min(values), 3),
                "max_ms": round(max(values), 3),
            }
    return {
        "trace_count": count,
        "planned_tool_steps": sums("planned_tool_steps"),
        "executed_tool_steps": total_calls,
        "non_error_tool_calls": nonerror,
        "tool_error_count": sums("tool_errors"),
        "tool_call_nonerror_rate": (nonerror / total_calls if total_calls else None),
        "fully_executed_trace_count": sum(r["step_sequence_complete"] for r in details),
        "completed_report_count": sum(r["final_report_completed"] for r in details),
        "completed_report_rate": (sum(r["final_report_completed"] for r in details) / count if count else None),
        "search_evidence_rate": (sums("searches_with_evidence") / total_search if total_search else None),
        "answer_citation_page_match_rate":
            (sums("answer_citation_pages_matched") / total_citations if total_citations else None),
        "unknown_citation_page_count": sum(len(r["answer_unknown_citations"]) for r in details),
        "synthetic_trace_count": len(synthetic),
        "synthetic_trace_label_rate":
            (sum(r["synthetic_data_labeled"] for r in synthetic) / len(synthetic) if synthetic else None),
        "end_to_end_task_success_rate": None,
        "resume_success_rate": None,
        "timed_trace_count": len(timed),
        "node_latency_ms": node_latency or None,
        "token_usage": None,
        "human_fact_accuracy": None,
        "limitations": [
            "Only saved JSON traces are observed; failed attempts without saved traces are not counted.",
            "Trace sample may be selected/retried and does not represent an unbiased production benchmark.",
            "Report completion != externally scored research task success.",
            "Citation matching checks source/page identifiers only, not scientific factual support.",
            "Node timing is reported ONLY for new traces that contain timings_ms; older traces remain untimed.",
            "Completed-node timings exclude failed attempts, restart gaps, and checkpoint overhead; they are not end-to-end latency.",
            "API token usage, end-to-end attempts and resume attempts are not recorded in these saved traces.",
            "Synthetic CSV data are demonstration-only and not experimental evidence.",
        ],
    }


def _pretty_rate(rate: Any) -> str:
    return "N/A" if rate is None else f"{rate:.1%}"


def render_markdown(summary: Dict[str, Any], details: List[Dict[str, Any]]) -> str:
    lines = [
        "# ResearchAgent Day 4 — Saved Trace Evaluation",
        "",
        "> **Exploratory trace audit, not an independent scientific fact-check or deployment benchmark.**",
        "",
        f"Analyzed saved traces: **{summary['trace_count']}**",
        "",
        "## Observed indicators",
        "",
        "| Indicator | Value | Interpretation |",
        "|---|---:|---|",
        f"| Final report completion | {summary['completed_report_count']}/{summary['trace_count']} ({_pretty_rate(summary['completed_report_rate'])}) | Syntactically complete traces with recognized report status |",
        f"| Tool calls without reported execution error | {summary['non_error_tool_calls']}/{summary['executed_tool_steps']} ({_pretty_rate(summary['tool_call_nonerror_rate'])}) | A NO_EVIDENCE search is not an exception; evidence separately tracked |",
        f"| Searches with evidence | {_pretty_rate(summary['search_evidence_rate'])} | Search returns formatted paper/page markers |",
        f"| Answer citation page match | {_pretty_rate(summary['answer_citation_page_match_rate'])} | Citation page identifiers are in retrieved source set; NOT fact verification |",
        f"| Synthetic dataset explicitly labeled | {_pretty_rate(summary['synthetic_trace_label_rate'])} | Only traces using synthetic analysis |",
        "| Research task success | Not measured | Requires independent task criteria / human labels |",
        "| Resume success rate | Not measured | Requires logged restore attempts, not final trace alone |",
        (f"| Completed-node timing coverage | {summary['timed_trace_count']}/{summary['trace_count']} "
         "| Timings apply only to traces containing new instrumentation |"),
        "| Token usage | Not measured | Existing traces lack token accounting |",
        "",
        "## Per-trace checklist",
        "",
        "| Saved trace | Report completed | Tool errors | Evidence pages | Citation match | Synthetic label |",
        "|---|---|---:|---:|---|---|",
    ]
    for row in details:
        cited = "OK" if row["answer_citations_all_linked"] else "CHECK"
        labeled = ("OK" if row["synthetic_data_labeled"] else "CHECK") if row["synthetic_analysis_used"] else "N/A"
        lines.append(f"| `{row['file']}` | {'YES' if row['final_report_completed'] else 'NO'} "
                     f"| {row['tool_errors']} | {row['saved_search_source_pages']} | {cited} | {labeled} |")
    if summary["node_latency_ms"]:
        lines += ["", "## Completed-node latency (instrumented traces only)", "",
                  "| Node | Traces | Mean (ms) | Min (ms) | Max (ms) |",
                  "|---|---:|---:|---:|---:|"]
        for node, values in summary["node_latency_ms"].items():
            lines.append(f"| {node} | {values['sample_count']} | {values['mean_ms']:.3f} "
                         f"| {values['min_ms']:.3f} | {values['max_ms']:.3f} |")
        lines += ["", "These are accumulated durations of *completed* node executions. "
                  "The executor node can run multiple times per task; its metric is the sum. "
                  "Checkpoint resumes and failed requests are not included in task-level wall time."]
    lines += ["", "## Limitations and follow-up", ""]
    lines += [f"- {s}" for s in summary["limitations"]]
    lines += ["", "**Next:** run offline fault injection, then capture timestamped node events and GLM token usage for future runs.", ""]
    return "\n".join(lines)


def collect_files(inputs: Iterable[str]) -> List[Path]:
    files = []
    for text in inputs:
        p = Path(text)
        if p.is_dir():
            files.extend(sorted(p.glob("planned_agent_*.json")))
        elif p.is_file() and p.suffix.lower() == ".json":
            files.append(p)
        else:
            raise ValueError(f"Input is not an existing JSON file or directory: {text}")
    return list(dict.fromkeys(p.resolve() for p in files))


def main() -> None:
    parser = argparse.ArgumentParser(description="ResearchAgent Day 4 saved trace evaluation (offline)")
    parser.add_argument("--input", nargs="+", default=["outputs"], help="Output directory or JSON file(s)")
    parser.add_argument("--output-dir", default="eval_outputs", help="Folder for aggregate metrics/report")
    args = parser.parse_args()
    try:
        sources = collect_files(args.input)
        if not sources:
            parser.error("No planned_agent_*.json files were found. Restore local traces or use an archived outputs folder.")
        details = []
        for src in sources:
            try:
                details.append(assess_trace(src.name, json.loads(src.read_text(encoding="utf-8"))))
            except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
                parser.error(f"Invalid trace {src.name}: {exc}")
        summary = summarize(details)
        report = render_markdown(summary, details)
        dest = Path(args.output_dir)
        dest.mkdir(parents=True, exist_ok=True)
        bundle = {"schema_version": 1, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                  "source_count": len(sources), "summary": summary, "per_trace": details}
        json_path = dest / "day4_metrics.json"
        md_path = dest / "day4_report.md"
        json_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(report, encoding="utf-8")
        print(f"[OK] Audited {len(details)} saved traces (no GLM/API calls).")
        print(f"[OK] Reports completed: {summary['completed_report_count']}/{summary['trace_count']}")
        print(f"[OK] Tool calls without execution error: {summary['non_error_tool_calls']}/{summary['executed_tool_steps']}")
        print("[NOTE] Completion and citation checks do not establish scientific correctness.")
        print(f"[SAVED] {json_path}\n[SAVED] {md_path}")
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()

"""Offline Day 4 trace metric tests; stdlib only.
Run: python -m tests.test_day4_metrics
"""
from evaluation.trace_metrics import assess_trace, summarize, render_markdown


def example_trace(*, failed_analysis=False, unknown_citation=False):
    records = [
        {"id": 1, "action": "search_papers", "status": "EVIDENCE_FOUND", "source_refs": ["(paper07.pdf, p.7)"]},
        {"id": 2, "action": "mcp_analyze_csv", "status": "TOOL_ERROR" if failed_analysis else "ANALYSIS_OK",
         "analysis_result": None if failed_analysis else {
             "provenance_warning": "SYNTHETIC DEMONSTRATION DATA", "status": "OK"}},
    ]
    return {
        "task": "Demo only",
        "plan": {"steps": [
            {"id": 1, "action": "search_papers"},
            {"id": 2, "action": "mcp_analyze_csv"},
            {"id": 3, "action": "final_answer"}]},
        "records": records,
        "refs": ["(paper07.pdf, p.7)"],
        "answer": ("合成数据，仅用于演示 (paper07.pdf, p.7)。"
                   + ("错误引用 (paper99.pdf, p.1)。" if unknown_citation else "")),
        "status": ("PARTIAL_ANALYSIS_FAILED_NOT_FACT_CHECKED" if failed_analysis else
                   "SOURCES_LINKED_NOT_FACT_CHECKED"),
        "issues": ["STEP_2: TOOL_ERROR"] if failed_analysis else [],
    }


def main():
    good = assess_trace("good.json", example_trace())
    assert good["final_report_completed"] and good["analysis_successes"] == 1
    assert good["answer_citations_all_linked"] and good["synthetic_data_labeled"]
    print("[PASS] Completed trace, source/page match and synthetic provenance labeled")

    bad = assess_trace("bad.json", example_trace(failed_analysis=True))
    assert bad["tool_errors"] == 1 and bad["tool_calls_without_error"] == 1
    assert bad["final_report_completed"]
    print("[PASS] Tool failure counted separately from partial report completion")

    missing = assess_trace("unknown.json", example_trace(unknown_citation=True))
    assert not missing["answer_citations_all_linked"] and missing["answer_unknown_citations"] == ["(paper99.pdf, p.1)"]
    print("[PASS] Unsupported paper/page citation flagged")

    aggregate = summarize([good, bad, missing])
    assert aggregate["trace_count"] == 3 and aggregate["tool_error_count"] == 1
    assert aggregate["node_latency_ms"] is None and aggregate["human_fact_accuracy"] is None
    assert "Not measured" in render_markdown(aggregate, [good, bad, missing])
    print("[PASS] Aggregate denominators, missing timing and fact-check limitations")
    print("All Day 4 offline trace-metric tests passed.")


if __name__ == "__main__":
    main()

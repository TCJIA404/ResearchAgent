"""Day 4: deterministic fault-injection tests against actual LangGraph graph.
Run: python -m tests.test_day4_fault_injection
Requires existing project LangGraph/SQLite deps, but NO RAG server or GLM tokens.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from planned_workflow import build_workflow


class Message:
    def __init__(self, content):
        self.content = content


class FakeModel:
    def __init__(self, steps, fail_first_writer=False):
        self.steps = steps
        self.fail_first_writer = fail_first_writer
        self.planner_calls = 0
        self.writer_calls = 0

    def invoke(self, prompt):
        if "Only these actions are available" in prompt:
            self.planner_calls += 1
            return Message(json.dumps({"steps": self.steps}))
        self.writer_calls += 1
        if self.fail_first_writer and self.writer_calls == 1:
            raise TimeoutError("SIMULATED_WRITER_TIMEOUT")
        return Message("以下仅为模拟检索引用 (paper07.pdf, p.7)，非科学事实核验。")


class Search:
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    def invoke(self, arguments):
        self.calls += 1
        if self.fail:
            raise ConnectionError("SIMULATED_RAG_API_DOWN")
        return "Search query: hydrogen\n[1] (paper07.pdf, p.7) Mock excerpt only."


SEARCH = {"id": 1, "action": "search_papers", "objective": "Find a source", "query": "hydrogen gasification"}
FINAL = {"id": 2, "action": "final_answer", "objective": "Write report", "query": ""}
CONTEXT = {
    "dataset": "demo_gasification",
    "columns": ["temperature_C", "hydrogen_vol_pct"],
    "provenance_warning": "SYNTHETIC DEMONSTRATION DATA, not evidence",
    "analysis_backend": "mcp",
    "sha256": "offline-test-placeholder",
}


def test_unavailable_rag_fails_closed():
    model, search = FakeModel([SEARCH, FINAL]), Search(fail=True)
    graph = build_workflow(model, search, None)
    final = graph.invoke({"task": "Study simulated search outage"}, config={"recursion_limit": 30})
    assert search.calls == 1
    assert final["records"][0]["status"] == "TOOL_ERROR"
    assert final["status"] == "NO_EVIDENCE"
    assert model.writer_calls == 0, "Do not call Writer without credible source markers"
    print("[PASS] Simulated RAG outage -> TOOL_ERROR and NO_EVIDENCE (no invented report)")


def test_mcp_error_produces_partial_report():
    steps = [SEARCH, {
        "id": 2, "action": "mcp_analyze_csv", "objective": "Test tool failure", "query": "",
        "dataset": "demo_gasification", "operation": "correlation",
        "x": "temperature_C", "y": "hydrogen_vol_pct",
    }, {"id": 3, "action": "final_answer", "objective": "Write with limitations", "query": ""}]
    model, search = FakeModel(steps), Search()
    attempts = []

    def mcp_failure(dataset, operation, x, y):
        attempts.append((dataset, operation, x, y))
        raise RuntimeError("SIMULATED_MCP_SERVER_DOWN")

    graph = build_workflow(model, search, None, analysis_tool=mcp_failure, dataset_context=CONTEXT)
    result = graph.invoke({"task": "Compare source and synthetic CSV"}, config={"recursion_limit": 30})
    assert len(attempts) == 1 and search.calls == 1
    assert [r["status"] for r in result["records"]] == ["EVIDENCE_FOUND", "TOOL_ERROR"]
    assert result["status"] == "PARTIAL_ANALYSIS_FAILED_NOT_FACT_CHECKED"
    assert "CSV 分析步骤" in result["answer"]
    print("[PASS] Simulated MCP outage -> partial report with explicit failed-analysis warning")


def test_writer_timeout_recovers_at_checkpoint():
    from langgraph.checkpoint.sqlite import SqliteSaver

    model, search = FakeModel([SEARCH, FINAL], fail_first_writer=True), Search()
    cfg = {"configurable": {"thread_id": "day4_mock_timeout"}, "recursion_limit": 30}
    with TemporaryDirectory() as tmp:
        dbfile = Path(tmp) / "faults.sqlite"
        with SqliteSaver.from_conn_string(str(dbfile)) as saver:
            graph = build_workflow(model, search, None, checkpointer=saver)
            try:
                graph.invoke({"task": "Test writer timeout and resume"}, config=cfg)
            except TimeoutError as exc:
                assert "SIMULATED_WRITER_TIMEOUT" in str(exc)
            else:
                raise AssertionError("Injected Writer timeout did not occur")
            snapshot = graph.get_state(cfg)
            assert snapshot.next == ("writer",), snapshot.next
            assert len(snapshot.values.get("records", [])) == 1
            assert model.planner_calls == 1 and search.calls == 1
        with SqliteSaver.from_conn_string(str(dbfile)) as saver:
            graph = build_workflow(model, search, None, checkpointer=saver)
            final = graph.invoke(None, config=cfg)
            assert not graph.get_state(cfg).next
            assert final["status"] == "SOURCES_LINKED_NOT_FACT_CHECKED"
            assert model.planner_calls == 1 and search.calls == 1
            assert model.writer_calls == 2
    print("[PASS] Simulated Writer timeout -> SQLite resume, Planner/Search not rerun")


def main():
    test_unavailable_rag_fails_closed()
    test_mcp_error_produces_partial_report()
    test_writer_timeout_recovers_at_checkpoint()
    print("All Day 4 fault-injection tests passed (simulated faults, no live API calls).")


if __name__ == "__main__":
    main()

"""Day 3: real MCP protocol + LangGraph planner/executor + SQLite resume checks.

Run from D:\\ResearchAgent: python -m tests.test_day3_mcp_agent
No GLM or FastAPI calls; real MCP subprocess used in final check.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from planner import validate_plan
from planned_workflow import build_workflow
from mcp_analysis_bridge import analyze_csv_via_mcp


STEPS = [
    {"id": 1, "action": "search_papers", "objective": "Find paper evidence", "query": "gasification H2"},
    {"id": 2, "action": "mcp_analyze_csv", "objective": "Compute synthetic correlation", "query": "",
     "dataset": "demo_gasification", "operation": "correlation",
     "x": "temperature_C", "y": "hydrogen_vol_pct"},
    {"id": 3, "action": "final_answer", "objective": "Compare sources with local demo statistics", "query": ""},
]
CONTEXT = {
    "dataset": "demo_gasification",
    "columns": ["temperature_C", "hydrogen_vol_pct", "steam_fuel_ratio",
                "total_syngas_yield_Nm3_per_kg"],
    "provenance_warning": "SYNTHETIC DEMONSTRATION DATA; not experimental evidence",
    "analysis_backend": "mcp",
    "sha256": "offline-test-dataset-digest",
}


class Message:
    def __init__(self, content):
        self.content = content


class FakeModel:
    def __init__(self):
        self.planner_calls = 0
        self.writer_calls = 0

    def invoke(self, prompt):
        if "Only these actions are available" in prompt:
            assert "MCP STDIO MODE IS ACTIVE" in prompt
            self.planner_calls += 1
            return Message(json.dumps({"steps": STEPS}))
        self.writer_calls += 1
        return Message("文献证据 (paper07.pdf, p.7)。本地模拟数据不能用于实证推断。")


class FakeSearch:
    def __init__(self):
        self.calls = 0

    def invoke(self, args):
        self.calls += 1
        return "Query: gasification H2\n[1] (paper07.pdf, p.7) Source excerpt"


def validate_mcp_plans():
    valid = validate_plan({"steps": STEPS}, "Compare papers and demo CSV", CONTEXT)
    assert valid["steps"][1]["action"] == "mcp_analyze_csv"

    def must_reject(steps, context):
        try:
            validate_plan({"steps": steps}, "Compare papers and demo CSV", context)
        except ValueError:
            return
        raise AssertionError("Unsafe or inconsistent plan accepted")

    must_reject(STEPS, None)  # MCP not implicitly enabled
    must_reject(STEPS, {**CONTEXT, "analysis_backend": "direct"})
    must_reject([STEPS[0], {**STEPS[1], "dataset": "../private"}, STEPS[-1]], CONTEXT)
    must_reject([STEPS[0], {**STEPS[1], "x": "secret_key"}, STEPS[-1]], CONTEXT)
    must_reject([STEPS[0], {**STEPS[1], "action": "analyze_csv"}, STEPS[-1]], CONTEXT)
    print("[PASS] Planner authorizes MCP action only for trusted dataset/columns")


def verify_langgraph_resume():
    from langgraph.checkpoint.sqlite import SqliteSaver

    search = FakeSearch()
    model = FakeModel()
    mcp_calls = []

    def fake_mcp(dataset, operation, x, y):
        mcp_calls.append((dataset, operation, x, y))
        return {
            "status": "OK", "dataset": dataset, "operation": operation,
            "x": x, "y": y, "pearson_r": 0.8755451, "paired_rows": 16,
            "mcp_tool": "analyze_demo_csv", "transport": "stdio",
            "provenance_warning": "SYNTHETIC DEMONSTRATION DATA; not a scientific finding",
        }

    with TemporaryDirectory() as tmp:
        db = Path(tmp) / "test_agent.sqlite"
        cfg = {"configurable": {"thread_id": "mcp_agent_01"}, "recursion_limit": 30}
        with SqliteSaver.from_conn_string(str(db)) as saver:
            graph = build_workflow(model, search, None, analysis_tool=fake_mcp,
                                   dataset_context=CONTEXT, checkpointer=saver,
                                   interrupt_after=["verify_step"])
            partial = graph.invoke({"task": "Compare paper evidence and demo CSV"}, config=cfg)
            assert len(partial["records"]) == 1
            assert graph.get_state(cfg).next == ("executor",)
        # Reopening SQLite simulates a new process resuming the same thread.
        with SqliteSaver.from_conn_string(str(db)) as saver:
            graph = build_workflow(model, search, None, analysis_tool=fake_mcp,
                                   dataset_context=CONTEXT, checkpointer=saver)
            final = graph.invoke(None, config=cfg)
            assert not graph.get_state(cfg).next
            assert search.calls == 1 and model.planner_calls == 1
            assert model.writer_calls == 1 and len(mcp_calls) == 1
            assert [r["status"] for r in final["records"]] == ["EVIDENCE_FOUND", "ANALYSIS_OK"]
            mcp_result = final["records"][1]["analysis_result"]
            assert mcp_result["mcp_tool"] == "analyze_demo_csv"
            assert "模拟数据声明" in final["answer"]
    print("[PASS] LangGraph resumes SQLite and executes planned MCP step once")


def verify_real_mcp_protocol():
    result = analyze_csv_via_mcp("demo_gasification", "correlation",
                                 "temperature_C", "hydrogen_vol_pct")
    assert result["mcp_tool"] == "analyze_demo_csv"
    assert result["transport"] == "stdio"
    assert result["paired_rows"] == 16
    assert abs(result["pearson_r"] - 0.8755451036924878) < 0.0001
    print("[PASS] Real MCP Client -> Server -> Day2 analyzer works via stdio")


if __name__ == "__main__":
    validate_mcp_plans()
    verify_langgraph_resume()
    verify_real_mcp_protocol()
    print("All Day 3 Agent + MCP integration tests passed. Live GLM/RAG validation still required.")

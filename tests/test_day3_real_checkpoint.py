"""Day 3 live LangGraph/SQLite checkpoint test with mock model and tools.

Run: python -m tests.test_day3_real_checkpoint
No GLM API calls and no RAG server required.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from langgraph.checkpoint.sqlite import SqliteSaver

from planned_workflow import build_workflow


SEARCH_RESULT = "Search query: gasification\n[1] (paper07.pdf, p.7) Retrieved excerpt on steam-to-fuel ratio."


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeModel:
    def __init__(self, steps):
        self.steps = steps
        self.planner_calls = 0
        self.writer_calls = 0

    def invoke(self, prompt):
        if "Only these actions are available" in prompt:
            self.planner_calls += 1
            return FakeMessage(json.dumps({"steps": self.steps}))
        self.writer_calls += 1
        return FakeMessage("文献摘录已检索 (paper07.pdf, p.7)。模拟数据不属于实验证据。")


class FakeSearch:
    def __init__(self):
        self.calls = 0

    def invoke(self, payload):
        assert payload["top_k"] == 5
        self.calls += 1
        return SEARCH_RESULT


def config_for(thread_id):
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 30}


def resume_search_without_repeat():
    steps = [
        {"id": 1, "action": "search_papers", "objective": "Find evidence", "query": "gasification steam"},
        {"id": 2, "action": "final_answer", "objective": "Summarize evidence", "query": ""},
    ]
    model, search = FakeModel(steps), FakeSearch()
    with TemporaryDirectory() as tmp:
        db = Path(tmp) / "agent.sqlite"
        cfg = config_for("test_real_01")
        with SqliteSaver.from_conn_string(str(db)) as saver:
            graph = build_workflow(model, search, None, checkpointer=saver,
                                   interrupt_after=["verify_step"])
            partial = graph.invoke({"task": "Summarize gasification evidence"}, config=cfg)
            snapshot = graph.get_state(cfg)
            assert snapshot.next == ("writer",), snapshot.next
            assert len(partial["records"]) == 1
            assert search.calls == 1 and model.planner_calls == 1 and model.writer_calls == 0
        # The connection is closed. Reopen the SAME SQLite file in a new process-like context.
        with SqliteSaver.from_conn_string(str(db)) as saver:
            graph = build_workflow(model, search, None, checkpointer=saver)
            final = graph.invoke(None, config=cfg)
            assert not graph.get_state(cfg).next
            assert search.calls == 1, "Already-completed search was re-executed"
            assert model.planner_calls == 1, "Planner was re-executed"
            assert model.writer_calls == 1
            assert final["status"] == "SOURCES_LINKED_NOT_FACT_CHECKED"
            assert final["refs"] == ["(paper07.pdf, p.7)"]
    print("[PASS] SQLite restores real workflow without rerunning committed search or Planner")


def resume_mixed_search_csv():
    steps = [
        {"id": 1, "action": "search_papers", "objective": "Search literature", "query": "gasification hydrogen"},
        {"id": 2, "action": "analyze_csv", "objective": "Compute correlation", "query": "",
         "dataset": "demo_gasification", "operation": "correlation", "x": "temperature_C", "y": "hydrogen_vol_pct"},
        {"id": 3, "action": "final_answer", "objective": "Report results", "query": ""},
    ]
    context = {"dataset": "demo_gasification", "columns": ["temperature_C", "hydrogen_vol_pct"],
               "provenance_warning": "SYNTHETIC DEMONSTRATION DATA; not scientific evidence", "sha256": "fake-test-sha"}
    model, search = FakeModel(steps), FakeSearch()
    analysis_calls = []

    def analyze(dataset, operation, x, y):
        analysis_calls.append((dataset, operation, x, y))
        return {"status": "OK", "dataset": dataset, "operation": operation,
                "provenance_warning": context["provenance_warning"],
                "paired_rows": 16, "pearson_r": 0.875545, "x": x, "y": y}

    with TemporaryDirectory() as tmp:
        db = Path(tmp) / "agent.sqlite"
        cfg = config_for("test_mixed_01")
        with SqliteSaver.from_conn_string(str(db)) as saver:
            graph = build_workflow(model, search, None, analysis_tool=analyze,
                                   dataset_context=context, checkpointer=saver,
                                   interrupt_after=["verify_step"])
            partial = graph.invoke({"task": "Compare evidence and synthetic CSV correlation"}, config=cfg)
            assert len(partial["records"]) == 1
            assert graph.get_state(cfg).next == ("executor",)
        with SqliteSaver.from_conn_string(str(db)) as saver:
            graph = build_workflow(model, search, None, analysis_tool=analyze,
                                   dataset_context=context, checkpointer=saver)
            final = graph.invoke(None, config=cfg)
            assert [r["status"] for r in final["records"]] == ["EVIDENCE_FOUND", "ANALYSIS_OK"]
            assert len(analysis_calls) == 1 and search.calls == 1
            assert "模拟数据声明" in final["answer"]
            assert not graph.get_state(cfg).next
    print("[PASS] Resumed mixed workflow executes CSV analysis and labels synthetic provenance")


if __name__ == "__main__":
    resume_search_without_repeat()
    resume_mixed_search_csv()
    print("All Day 3 real-workflow SQLite tests passed.")

"""Day 4 timing and SQLite checkpoint compatibility tests.

Run in the existing thermowaste-agent Conda environment:
    python -m tests.test_day4_timing

Requires LangGraph + langgraph-checkpoint-sqlite already installed.
Uses fake model/tools; NO external API calls or real GLM tokens.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.trace_metrics import assess_trace, summarize, render_markdown
from planned_workflow import build_workflow


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeModel:
    def __init__(self):
        self.planner_calls = 0
        self.writer_calls = 0

    def invoke(self, prompt):
        if "Only these actions are available" in prompt:
            self.planner_calls += 1
            return FakeMessage(json.dumps({"steps": [
                {"id": 1, "action": "search_papers", "objective": "Retrieve evidence", "query": "gasification H2"},
                {"id": 2, "action": "final_answer", "objective": "Summarize", "query": ""},
            ]}))
        self.writer_calls += 1
        return FakeMessage("文献检索摘录 (paper07.pdf, p.7)，模拟测试并非科学事实核验。")


class FakeSearch:
    def __init__(self):
        self.calls = 0

    def invoke(self, arguments):
        self.calls += 1
        return "Search query: gasification\n[1] (paper07.pdf, p.7) Test excerpt only."


def main():
    model, search = FakeModel(), FakeSearch()
    from langgraph.checkpoint.sqlite import SqliteSaver

    cfg = {"configurable": {"thread_id": "timing_offline_01"}, "recursion_limit": 30}
    with TemporaryDirectory() as tmp:
        dbfile = Path(tmp) / "checkpoints.sqlite"
        with SqliteSaver.from_conn_string(str(dbfile)) as checkpointer:
            graph = build_workflow(model, search, None, checkpointer=checkpointer,
                                   interrupt_after=["verify_step"])
            paused = graph.invoke({"task": "Analyze gasification evidence"}, config=cfg)
            assert graph.get_state(cfg).next == ("writer",)
            assert len(paused["records"]) == 1
            assert model.planner_calls == 1 and search.calls == 1
            saved_timings = paused["timings_ms"]
            assert all(key in saved_timings for key in
                       ("planner_ms", "executor_ms", "verifier_ms"))
            assert paused["records"][0]["latency_ms"] >= 0
        print("[PASS] Planner/Executor/Verifier timers persisted in SQLite checkpoint")

        with SqliteSaver.from_conn_string(str(dbfile)) as checkpointer:
            graph = build_workflow(model, search, None, checkpointer=checkpointer)
            finished = graph.invoke(None, config=cfg)
            assert graph.get_state(cfg).next == ()
            assert model.planner_calls == 1 and model.writer_calls == 1 and search.calls == 1
            assert finished["timings_ms"]["planner_ms"] == saved_timings["planner_ms"]
            assert finished["timings_ms"]["executor_ms"] == saved_timings["executor_ms"]
            assert finished["timings_ms"]["verifier_ms"] == saved_timings["verifier_ms"]
            assert finished["timings_ms"]["writer_ms"] >= 0
        print("[PASS] Writer timer added after resume; previously committed nodes not rerun")

    updated = assess_trace("timed.json", finished)
    assert updated["node_timings_available"]
    assert set(updated["node_timings_ms"]) == {
        "planner_ms", "executor_ms", "verifier_ms", "writer_ms"}
    assert len(updated["tool_latencies_ms"]) == 1
    old = dict(finished)
    old.pop("timings_ms", None)
    old["records"] = [{k: v for k, v in r.items() if k != "latency_ms"} for r in old["records"]]
    older = assess_trace("old.json", old)
    assert not older["node_timings_available"]
    aggregate = summarize([updated, older])
    assert aggregate["timed_trace_count"] == 1 and aggregate["trace_count"] == 2
    assert aggregate["node_latency_ms"]["writer_ms"]["sample_count"] == 1
    assert "Completed-node latency" in render_markdown(aggregate, [updated, older])
    print("[PASS] Evaluation reports node latency without assigning invented values to older traces")
    print("All Day 4 timing tests passed (fake model/tools; no live API calls).")


if __name__ == "__main__":
    main()

"""Day 2 integrated offline tests. Run with:
    python -m tests.test_day2_integrated_workflow
Requires the existing thermowaste-agent LangGraph environment, no GLM or API.
"""
import json
import tempfile
from pathlib import Path

from data_analysis_tool import analyze_csv
from planner import validate_plan
from planned_workflow import build_workflow, write_evidence_answer

CONTEXT = {
    "dataset": "demo_gasification",
    "columns": ["temperature_C", "steam_fuel_ratio", "hydrogen_vol_pct",
                "total_syngas_yield_Nm3_per_kg"],
    "provenance_warning": "SYNTHETIC DEMONSTRATION DATA; not experimental evidence",
}

PLAN = {"steps": [
    {"id": 1, "action": "search_papers", "objective": "Search gasification evidence",
     "query": "How does gasification temperature affect hydrogen concentration?"},
    {"id": 2, "action": "analyze_csv", "objective": "Calculate demo correlation",
     "query": "", "dataset": "demo_gasification", "operation": "correlation",
     "x": "temperature_C", "y": "hydrogen_vol_pct"},
    {"id": 3, "action": "analyze_csv", "objective": "Plot demo correlation",
     "query": "", "dataset": "demo_gasification", "operation": "scatter_plot",
     "x": "temperature_C", "y": "hydrogen_vol_pct"},
    {"id": 4, "action": "final_answer", "objective": "Discuss literature and demo separately",
     "query": ""},
]}


class Msg:
    def __init__(self, content):
        self.content = content


class FakeModel:
    def __init__(self, plan=PLAN, report="文献指出需考虑多种工况 (paper07.pdf, p.7)。"):
        self.plan = plan
        self.report = report
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        if "Only these actions are available" in prompt:
            return Msg(json.dumps(self.plan, ensure_ascii=False))
        return Msg(self.report)


class FakeSearch:
    def __init__(self, result="Search query: test\n[1] (paper07.pdf, p.7) Steam gasification compared."):
        self.result = result
        self.calls = []

    def invoke(self, args):
        self.calls.append(args)
        return self.result


def reject(plan, context):
    try:
        validate_plan(plan, "Compare gasification evidence with demo data", context)
    except ValueError:
        return
    raise AssertionError("Unsafe plan was accepted: " + repr(plan))


def main():
    sample = validate_plan(PLAN, "Compare gasification evidence with demo data", CONTEXT)
    assert sample["steps"][1]["operation"] == "correlation"
    assert [s["action"] for s in sample["steps"]] == [
        "search_papers", "analyze_csv", "analyze_csv", "final_answer"]
    print("[PASS] Planner validates mixed literature and CSV analysis plan")

    import copy
    unknown_dataset = copy.deepcopy(PLAN)
    unknown_dataset["steps"][1]["dataset"] = "../.env.agent"
    reject(unknown_dataset, CONTEXT)
    bad_col = copy.deepcopy(PLAN)
    bad_col["steps"][1]["x"] = "not_a_real_column"
    reject(bad_col, CONTEXT)
    dangerous_op = copy.deepcopy(PLAN)
    dangerous_op["steps"][1]["operation"] = "python_exec"
    reject(dangerous_op, CONTEXT)
    reject(PLAN, None)
    no_analysis = {"steps": [PLAN["steps"][0],
                             {"id": 2, "action": "final_answer", "objective": "finish", "query": ""}]}
    reject(no_analysis, CONTEXT)
    print("[PASS] Unsafe dataset, columns, operations and missing analysis rejected")

    with tempfile.TemporaryDirectory() as tmp:
        call_log = []

        def analysis_tool(dataset, operation, x, y):
            call_log.append((dataset, operation, x, y))
            return analyze_csv(dataset, operation, x, y, output_dir=Path(tmp))

        fake_model, fake_search = FakeModel(), FakeSearch()
        result = build_workflow(fake_model, fake_search, None,
                                analysis_tool=analysis_tool, dataset_context=CONTEXT).invoke(
                                    {"task": "Compare temperature and hydrogen"},
                                    config={"recursion_limit": 30})
        assert len(fake_search.calls) == 1 and len(call_log) == 2
        assert result["cursor"] == 3
        assert [r["status"] for r in result["records"]] == [
            "EVIDENCE_FOUND", "ANALYSIS_OK", "ANALYSIS_OK"]
        assert 0.87 < result["records"][1]["analysis_result"]["pearson_r"] < 0.89
        chart = Path(result["records"][2]["analysis_result"]["chart_path"])
        assert chart.is_file() and chart.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert "模拟数据声明" in result["answer"]
        assert result["status"] == "SOURCES_LINKED_NOT_FACT_CHECKED"
        assert "SYNTHETIC" in fake_model.prompts[-1]
    print("[PASS] LangGraph executes search, CSV statistics, real PNG, verifier, writer")

    def failing_analysis(dataset, operation, x, y):
        raise ValueError("Simulated safe tool failure")

    failure = build_workflow(FakeModel(), FakeSearch(), None,
                             analysis_tool=failing_analysis, dataset_context=CONTEXT).invoke(
                                 {"task": "Compare data"}, config={"recursion_limit": 30})
    assert "PARTIAL_ANALYSIS_FAILED" in failure["status"]
    assert any("TOOL_ERROR" in i for i in failure["issues"])
    assert "执行限制" in failure["answer"]
    print("[PASS] Failed CSV analysis is flagged and not reported as success")

    no_literature = build_workflow(FakeModel(), FakeSearch("No passages found."), None,
                                   analysis_tool=analyze_csv, dataset_context=CONTEXT).invoke(
                                       {"task": "Compare data"}, config={"recursion_limit": 30})
    assert no_literature["status"] == "NO_EVIDENCE"
    print("[PASS] No literature evidence blocks scientific report despite CSV results")
    print("All Day 2 integrated workflow offline tests passed.")


if __name__ == "__main__":
    main()

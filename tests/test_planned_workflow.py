"""Run in thermowaste-agent: python -m tests.test_planned_workflow"""
import json
from planned_workflow import build_workflow, source_refs, write_evidence_answer

PLAN = {"steps": [
    {"id": 1, "action": "search_papers", "objective": "Find temperature evidence",
     "query": "How does temperature affect H2?"},
    {"id": 2, "action": "search_papers", "objective": "Find steam ratio evidence",
     "query": "How does steam fuel ratio affect H2?"},
    {"id": 3, "action": "final_answer", "objective": "Compare conditions", "query": ""},
]}


class Msg:
    def __init__(self, content):
        self.content = content


class FakeModel:
    def __init__(self, answer="结论受条件影响，文献报告存在差异 (paper07.pdf, p.7)。"):
        self.calls = []
        self.answer = answer

    def invoke(self, prompt):
        self.calls.append(prompt)
        if "Only these actions are available" in prompt:
            return Msg(json.dumps(PLAN))
        return Msg(self.answer)


class FakeTool:
    def __init__(self, outputs):
        self.calls = []
        self.outputs = list(outputs)

    def invoke(self, kwargs):
        self.calls.append(kwargs)
        return self.outputs.pop(0)


def main():
    src = "Search query: q\n[1] (paper07.pdf, p.7) Temperature was varied.\n[2] (paper09.pdf, p.8) Gas yields changed."
    assert source_refs(src) == ["(paper07.pdf, p.7)", "(paper09.pdf, p.8)"]
    assert source_refs("TOOL_ERROR: unavailable") == []
    print("[PASS] Source/page references parsed only from search wrappers")

    tool = FakeTool([src, "Search query: q\n[1] (paper07.pdf, p.7) Steam addition varied."])
    model = FakeModel()
    graph = build_workflow(model, tool, FakeTool([]))
    result = graph.invoke({"task": "Compare gasification variables"}, config={"recursion_limit": 30})
    assert len(tool.calls) == 2 and len(result["records"]) == 2
    assert result["status"] == "SOURCES_LINKED_NOT_FACT_CHECKED"
    assert "(paper07.pdf, p.7)" in result["answer"]
    assert len(result["refs"]) == 2
    assert result["cursor"] == 2
    print("[PASS] LangGraph planner -> two real steps (mock tools) -> verifier -> writer")

    uncited = write_evidence_answer(FakeModel("Without any citation."), "Question", result["records"], result["refs"])
    assert uncited["status"] == "BLOCKED_UNCITED_ANSWER"
    print("[PASS] Answer without source/page citation blocked")

    fake_cited = write_evidence_answer(FakeModel("Unsupported (paper99.pdf, p.1)."), "Question", result["records"], result["refs"])
    assert fake_cited["status"] == "BLOCKED_UNSUPPORTED_CITATIONS"
    print("[PASS] Hallucinated citation blocked")

    bad = FakeTool(["TOOL_ERROR: offline", "No passages found in the corpus."])
    failed = build_workflow(FakeModel(), bad, FakeTool([])).invoke({"task": "Question"}, config={"recursion_limit": 30})
    assert failed["status"] == "NO_EVIDENCE" and len(failed["issues"]) >= 2
    print("[PASS] Retrieval failures fail closed, no invented answer")

    print("All offline planned-workflow tests passed.")


if __name__ == "__main__":
    main()

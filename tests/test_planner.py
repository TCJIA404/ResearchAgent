"""Offline planner tests: run with python -m tests.test_planner."""
import json

from planner import generate_plan, validate_plan

GOOD = {"steps": [
    {"id": 1, "action": "search_papers", "objective": "Find temperature evidence",
     "query": "How does gasification temperature affect H2 yield?"},
    {"id": 2, "action": "search_papers", "objective": "Find steam ratio evidence",
     "query": "How does steam fuel ratio affect H2 concentration?"},
    {"id": 3, "action": "final_answer", "objective": "Compare findings and cite limitations", "query": ""},
]}


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeModel:
    def __init__(self, payload, fenced=False):
        body = json.dumps(payload, ensure_ascii=False)
        self.response = "```json\n{}\n```".format(body) if fenced else body

    def invoke(self, prompt):
        assert "search_papers" in prompt and "final_answer" in prompt
        return FakeMessage(self.response)


def rejected(plan):
    try:
        validate_plan(plan, "Analyze gasification effects")
    except ValueError:
        return True
    return False


def main():
    task = "Compare temperature and steam ratio effects on H2 production"
    plan = generate_plan(task, FakeModel(GOOD))
    assert plan["task"] == task and len(plan["steps"]) == 3
    print("[PASS] Valid plan generated and normalized")

    plan = generate_plan(task, FakeModel(GOOD, fenced=True))
    assert plan["steps"][-1]["action"] == "final_answer"
    print("[PASS] Markdown-fenced JSON handled")

    bad_tool = json.loads(json.dumps(GOOD))
    bad_tool["steps"][1]["action"] = "delete_files"
    assert rejected(bad_tool)
    print("[PASS] Unsupported tool rejected")

    bad_sequence = json.loads(json.dumps(GOOD))
    bad_sequence["steps"][0]["id"] = 5
    assert rejected(bad_sequence)
    print("[PASS] Invalid step order rejected")

    no_evidence = {"steps": [
        {"id": 1, "action": "ask_rag", "objective": "Ask model", "query": "Some question"},
        {"id": 2, "action": "final_answer", "objective": "Synthesize", "query": ""},
    ]}
    assert rejected(no_evidence)
    print("[PASS] Missing evidence retrieval rejected")

    try:
        generate_plan("", FakeModel(GOOD))
        raise AssertionError("Empty task was accepted")
    except ValueError:
        print("[PASS] Empty task rejected")
    print("All offline planner tests passed.")


if __name__ == "__main__":
    main()

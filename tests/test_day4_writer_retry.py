"""Offline Writer-only retry diagnostics; does not invoke GLM or RAG."""
from scripts.retry_writer import inspect, retry


class Msg:
    def __init__(self, content):
        self.content = content


class FakeModel:
    def __init__(self, content):
        self.content = content
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return Msg(self.content)


def main():
    trace = {
        "task": "Demo temperature effects",
        "status": "BLOCKED_UNCITED_ANSWER",
        "refs": ["(paper07.pdf, p.7)"],
        "records": [{"id": 1, "action": "search_papers", "status": "EVIDENCE_FOUND",
                     "query": "temperature H2", "output": "[1] (paper07.pdf, p.7) Steam ratio affects H2 concentration."}],
    }
    info = inspect(trace)
    assert info["search_ref_parse_crosscheck"] == trace["refs"]
    print("[PASS] Inspect saved trace without any network requests")

    m = FakeModel("文献显示蒸汽比影响氢浓度 (paper07.pdf, p.7)。")
    result, draft = retry(trace, m)
    assert result["status"] == "SOURCES_LINKED_NOT_FACT_CHECKED"
    assert draft == m.content and len(m.prompts) == 1
    assert "exact allowed citation" in m.prompts[0]
    print("[PASS] Retry validates an actually cited draft")

    result, draft = retry(trace, FakeModel("文献表明一种趋势，但未写来源。"))
    assert result["status"] == "BLOCKED_UNCITED_ANSWER"
    print("[PASS] Missing citations remain blocked; nothing is auto-attached")

    result, draft = retry(trace, FakeModel("错误引用 (paper99.pdf, p.9)。"))
    assert result["status"] == "BLOCKED_UNSUPPORTED_CITATIONS"
    print("[PASS] Invented citation remains blocked")
    print("All Writer-only retry tests passed (no live API calls).")


if __name__ == "__main__":
    main()

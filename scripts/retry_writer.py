"""Retry only the Writer from a saved ResearchAgent trace.

Does not modify existing SQLite checkpoints or the source JSON trace.
Do not count this as an independent research task in evaluation metrics.

Usage:
  python -m scripts.retry_writer --trace outputs/planned_agent_xxx.json --inspect
  python -m scripts.retry_writer --trace outputs/planned_agent_xxx.json --retry
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from planned_workflow import source_refs, write_evidence_answer


class CitationFocusedModel:
    """Prompt-only formatting guidance; existing strict verifier remains in control."""

    def __init__(self, model):
        self.model = model
        self.last_draft = None

    def invoke(self, prompt):
        prompt += (
            "\n\nIMPORTANT FINAL OUTPUT CONSTRAINTS:\n"
            "- Write a SHORT Chinese report of about 500-900 Chinese characters.\n"
            "- Begin the LITERATURE section with a substantive evidence-backed claim and "
            "an exact allowed citation in this format: (paper07.pdf, p.7) "
            "(replace the example with the source/page actually supporting the claim).\n"
            "- Every factual statement about a PDF must carry an exact supported "
            "(filename.pdf, p.N) citation. Do NOT add generic or decorative citations.\n"
            "- If a claim is unsupported by the provided excerpts, omit it or explicitly "
            "say the excerpts do not establish it.\n"
            "- Keep synthetic CSV results in a separate section and label them synthetic.\n"
            "- Do not cite reference-list pages as evidence of experimental findings.\n"
        )
        response = self.model.invoke(prompt)
        content = getattr(response, "content", response)
        self.last_draft = content if isinstance(content, str) else str(content)
        return response


def inspect(trace):
    records = trace.get("records") or []
    return {
        "task": trace.get("task", ""),
        "saved_status": trace.get("status", "UNKNOWN"),
        "record_count": len(records),
        "search_source_refs": trace.get("refs", []),
        "tool_statuses": [
            {"step": r.get("id"), "action": r.get("action"), "status": r.get("status")}
            for r in records
        ],
        "search_ref_parse_crosscheck": sorted({
            ref for r in records if r.get("action") == "search_papers"
            for ref in source_refs(r.get("output", ""))
        }),
    }


def retry(trace, model):
    if not trace.get("refs") or not trace.get("records"):
        raise ValueError("Trace lacks grounded references or tool records; cannot retry Writer")
    focused = CitationFocusedModel(model)
    result = write_evidence_answer(focused, trace["task"], trace["records"], trace["refs"])
    return result, focused.last_draft


def main():
    parser = argparse.ArgumentParser(description="Inspect or retry Writer from existing saved trace")
    parser.add_argument("--trace", required=True, help="Path to existing planned_agent_*.json")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--inspect", action="store_true", help="No network calls")
    action.add_argument("--retry", action="store_true", help="Make ONE GLM Writer call")
    args = parser.parse_args()
    trace_file = Path(args.trace)
    trace = json.loads(trace_file.read_text(encoding="utf-8"))
    if args.inspect:
        print(json.dumps(inspect(trace), ensure_ascii=False, indent=2))
        return
    from research_agent import create_model
    model = create_model()
    if hasattr(model, "bind"):
        model = model.bind(timeout=180, max_tokens=1600)
    result, draft = retry(trace, model)
    out_dir = Path("outputs") / "writer_retries"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = "writer_retry_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    payload = {"original_trace": str(trace_file), "retry_not_new_task": True, **result}
    dest = out_dir / (stem + ".json")
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if result["status"].startswith("BLOCKED") and isinstance(draft, str):
        # Local debugging only. outputs/ must remain gitignored.
        (out_dir / (stem + "_blocked_draft.txt")).write_text(draft, encoding="utf-8")
    print("Writer retry status: " + result["status"])
    print("Saved retry result: " + str(dest))
    print("Note: original trace and SQLite checkpoints were not changed.")
    if result["status"].startswith("BLOCKED"):
        print("Blocked draft saved locally for citation-format inspection. Do not publish it.")


if __name__ == "__main__":
    main()

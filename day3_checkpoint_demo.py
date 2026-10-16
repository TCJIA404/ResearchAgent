"""Day 3: Verify LangGraph SQLite checkpoint and resume across process restarts.

Standalone example: no RAG server, GLM key, or real CSV files are needed.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph


class DemoState(TypedDict, total=False):
    task: str
    completed: list[str]
    evidence: str
    analysis: str
    report: str


def safe_thread_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise ValueError("thread-id must be 1-64 letters, digits, '-' or '_'")
    return value


def event_counts(log_file: Path) -> dict[str, int]:
    if not log_file.exists():
        return {}
    return dict(Counter(line.strip() for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()))


def build_graph(checkpointer: SqliteSaver, event_file: Path):
    def record(name: str) -> None:
        event_file.parent.mkdir(parents=True, exist_ok=True)
        with event_file.open("a", encoding="utf-8") as handle:
            handle.write(name + "\n")

    def search_node(state: DemoState) -> dict:
        record("search")
        return {
            "completed": [*state.get("completed", []), "search"],
            "evidence": "Mock evidence only (no actual research paper fetched)",
        }

    def analysis_node(state: DemoState) -> dict:
        record("analysis")
        return {
            "completed": [*state.get("completed", []), "analysis"],
            "analysis": "Mock analysis only (no actual CSV computation)",
        }

    def writer_node(state: DemoState) -> dict:
        record("writer")
        return {
            "completed": [*state.get("completed", []), "writer"],
            "report": "DEMO ONLY: checkpoint/resume verified; no scientific conclusion generated.",
        }

    builder = StateGraph(DemoState)
    builder.add_node("search", search_node)
    builder.add_node("analysis", analysis_node)
    builder.add_node("writer", writer_node)
    builder.add_edge(START, "search")
    builder.add_edge("search", "analysis")
    builder.add_edge("analysis", "writer")
    builder.add_edge("writer", END)

    # For the first invocation, stop *after* a completed node and checkpoint.
    # Next invocation with None + the same thread_id resumes at 'analysis'.
    return builder.compile(checkpointer=checkpointer, interrupt_after=["search"])


def run(action: str, thread_id: str, task: str, root: Path) -> dict:
    thread_id = safe_thread_id(thread_id)
    root.mkdir(parents=True, exist_ok=True)
    db_file = root / "day3_checkpoint_demo.sqlite"
    event_file = root / f"day3_events_{thread_id}.log"
    config = {"configurable": {"thread_id": thread_id}}

    # Context manager closes the DB connection so a new process can reopen it.
    with SqliteSaver.from_conn_string(str(db_file)) as saver:
        graph = build_graph(saver, event_file)
        before = graph.get_state(config)
        present = bool(before.values)

        if action == "start":
            if present:
                raise ValueError("This thread already exists. Choose a new thread-id or use --action resume/status.")
            graph.invoke({"task": task, "completed": []}, config=config)
        elif action == "resume":
            if not present:
                raise ValueError("No saved state found for thread-id; run --action start first.")
            if before.next:
                graph.invoke(None, config=config)
        elif action != "status":
            raise ValueError("Unsupported action")

        snapshot = graph.get_state(config)
        value = snapshot.values or {}
        return {
            "action": action,
            "thread_id": thread_id,
            "db_file": str(db_file),
            "saved": bool(value),
            "next_nodes": list(snapshot.next or []),
            "completed": value.get("completed", []),
            "event_counts": event_counts(event_file),
            "report": value.get("report", ""),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Day 3 SQLite checkpoint/resume demo")
    parser.add_argument("--action", required=True, choices=["start", "resume", "status"])
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--task", default="Demo literature analysis")
    parser.add_argument("--db-dir", default="checkpoints")
    args = parser.parse_args()
    try:
        result = run(args.action, args.thread_id, args.task, Path(args.db_dir))
    except (ValueError, OSError) as exc:
        parser.exit(status=2, message=f"ERROR: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

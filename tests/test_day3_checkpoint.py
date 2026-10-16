"""Offline functional test (requires LangGraph + SQLite checkpointer)."""
from pathlib import Path
from tempfile import TemporaryDirectory

from day3_checkpoint_demo import run


def test_resume() -> None:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        first = run("start", "test_thread_01", "demo task", root)
        assert first["saved"]
        assert first["completed"] == ["search"], first
        assert first["next_nodes"] == ["analysis"], first
        assert first["event_counts"].get("search") == 1, first
        print("[PASS] Search node checkpointed before interruption")

        # Reopen SQLite using a new saver instance, simulating process restart.
        second = run("resume", "test_thread_01", "ignored", root)
        assert second["next_nodes"] == [], second
        assert second["completed"] == ["search", "analysis", "writer"], second
        assert second["event_counts"] == {"search": 1, "analysis": 1, "writer": 1}, second
        print("[PASS] Resume completed graph without re-running search")

        third = run("resume", "test_thread_01", "ignored", root)
        assert third["event_counts"] == second["event_counts"], third
        print("[PASS] Repeated resume of completed thread did not duplicate work")

        other = run("start", "test_thread_02", "separate", root)
        assert other["completed"] == ["search"], other
        print("[PASS] Different thread_ids keep independent state")


if __name__ == "__main__":
    test_resume()
    print("All Day 3 SQLite checkpoint tests passed.")

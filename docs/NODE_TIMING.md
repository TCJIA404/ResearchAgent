# ResearchAgent Day 4 — Node Latency Instrumentation

## What changes

1. `planned_workflow.py`: measures completed-node durations using `time.perf_counter()` for Planner, Executor, Verifier, and Writer. Tool step durations are also attached to each `records[]` entry under `latency_ms`. The `timings_ms` dictionary is part of LangGraph state and accumulates across SQLite checkpoints.
2. `evaluation/trace_metrics.py`: reads `timings_ms` when present, calculates per-node mean/min/max with explicit sample counts, keeps older traces unmeasured, and outputs an updated Markdown report.
3. `tests/test_day4_timing.py`: offline simulation of checkpoint pause and resume; verifies no duplicate Planner or Search calls and mixed old/new evaluation.

## Installation

Make a backup in `D:\ResearchAgent` first:

```cmd
cd /d D:\ResearchAgent
copy planned_workflow.py planned_workflow_pre_timing.py
copy evaluation\trace_metrics.py evaluation\trace_metrics_pre_timing.py
```

Extract this ZIP into `D:\ResearchAgent` and **replace only** the matching source files.
Keep your local `.env.agent`, `outputs/`, `checkpoints/` and old backups out of public Git.

## Tests (no GLM API calls)

```cmd
python -m tests.test_day4_metrics
python -m tests.test_day4_fault_injection
python -m tests.test_day4_timing
python -m tests.test_day3_mcp_agent
```

Run the first real instrumentation on a **new thread ID** after tests pass. Ensure your RAG FastAPI service is running:

```cmd
python -u planned_workflow.py --task "Compare gasification temperature effects on hydrogen concentration using literature evidence" --thread-id timing_demo_001 --save
```

A fresh run incurs GLM API calls and may take minutes. It should save `outputs/planned_agent_*.json` containing `timings_ms` and `records[].latency_ms`. Do not use the already-completed `mcp_demo_001`: it cannot retroactively produce timings.

Rebuild the report:

```cmd
python -m evaluation.trace_metrics --input outputs --output-dir eval_outputs
```

## Interpretation and scope

- `planner_ms`: one successful Planner execution.
- `executor_ms`: accumulated time across **all** successful Executor node visits, including failed tool calls that were caught and returned as `TOOL_ERROR`.
- `verifier_ms`: sum of completed verification visits.
- `writer_ms`: completed Writer time, which includes GLM response and citation-format checks.
- `records[].latency_ms`: elapsed duration of an individual tool step.
- Old traces retain null timing fields; per-node summary sample sizes can differ and **must be shown**.

**Important:** completed-node timers are not end-to-end wall-clock time. Failed GLM attempts, program restarts, SQLite overhead and waiting between pauses do **not** appear in these totals. In particular a Writer timeout followed by success may be reported as only the successful Writer invocation. Real-world reliability requires separate attempt/failure logs.

These timings do not measure Token usage. Citation-page matching is not scientific fact verification. Synthetic CSV remains synthetic demonstration data.

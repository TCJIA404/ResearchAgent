# ResearchAgent — Recoverable Multi-tool Scientific Research Agent

[简体中文](README.md) | [English](README_EN.md)

ResearchAgent is a **LangGraph planner–executor–verifier–writer prototype** integrating an external literature RAG API, constrained CSV analysis, a real MCP stdio client/server, and SQLite checkpointing. It is intended for engineering demonstration and assisted literature analysis, **not independently verified scientific findings**.

## Demonstrated capabilities

- GLM produces a JSON plan which is validated against permitted tool names and dataset columns.
- `search_papers`/`ask_rag` call the separate ThermoWaste-RAG FastAPI service via HTTP.
- `analyze_csv` computes descriptive statistics, Pearson correlation and scatter plots using pandas/matplotlib.
- `mcp_analyze_csv` calls an allow-listed tool over the actual MCP stdio protocol.
- LangGraph SQLite checkpoints support resuming after previously committed graph nodes.
- Citation provenance is matched to retrieved `(paperXX.pdf, p.N)` markers; **scientific factual support is not established by this check**.

## Quick start (Windows, Python 3.11)

```cmd
conda create -n thermowaste-agent python=3.11 -y
conda activate thermowaste-agent
cd /d D:\ResearchAgent
python -m pip install -r requirements.txt
copy .env.agent.example .env.agent
```

Edit the private `.env.agent` with `AGENT_API_KEY`, `AGENT_BASE_URL`, `AGENT_MODEL`, and `RAG_API_URL`. Start your existing RAG API in a separate terminal.

```cmd
python research_agent.py --question "How does gasification temperature affect hydrogen production?" --audit
python -u planned_workflow.py --task "Compare gasification temperature effects on hydrogen production" --save
python -u planned_workflow.py --task "Compare gasification evidence with synthetic demo data; calculate correlation and plot" --dataset demo_gasification --mcp --thread-id demo_101 --pause-after-step
python -u planned_workflow.py --resume --thread-id demo_101 --save
```

The synthetic 16-row CSV is a **software-test fixture, not experimental evidence**. The RAG corpus, SQLite checkpoints, traces and credentials are not bundled. For implementation details and limitations, refer to [the full Chinese README](README.md) and the `docs/` directory.


## Reliability and evaluation (Day 4)

Across **six saved traces** (four completed and two blocked), four contain completed reports; 17 of 18 tool invocations have no logged execution error. The original four completed traces contained 12/12 non-error tool calls. These selected traces **do not measure end-to-end task success or scientific factual correctness**. Separately observed failures include an unavailable RAG server (`NO_EVIDENCE`) and a blocked draft lacking required citations (`BLOCKED_UNCITED_ANSWER`). A one-off Writer retry reused saved evidence and passed citation-provenance matching while preserving the original failed trace. Simulated RAG/MCP/Writer failure tests passed.

One measured run took approximately 14.39 s in Planner, 6.18 s in Executor, 0.059 ms in Verifier, and 61.43 s in Writer. These are accumulated completed-node durations, not a representative benchmark or end-to-end wall-clock duration. See [Day 4 metrics and limitations](docs/DAY4_RESULTS.md), [publishing guide](docs/GITHUB_RELEASE_STEPS.md) and [interview notes](docs/INTERVIEW_NOTES.md).

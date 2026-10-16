# Day 4: Retry only the Writer from a saved trace

The last task's RAG and MCP tool calls succeeded, but the Writer draft contained no citation markers matching `(paperXX.pdf, p.N)`. This script can inspect the saved evidence without network calls, then make **one optional GLM call** to regenerate only the Writer report.

1. Copy `scripts/retry_writer.py` and `tests/test_day4_writer_retry.py` into the matching folders in `D:\ResearchAgent`.
2. Run `python -m tests.test_day4_writer_retry`.
3. Inspect existing evidence without spending tokens:
   `python -m scripts.retry_writer --trace outputs/planned_agent_20261012_164955_648527.json --inspect`
4. Optionally retry the Writer (GLM tokens and time required):
   `python -m scripts.retry_writer --trace outputs/planned_agent_20261012_164955_648527.json --retry`

This does **not** repeat RAG or MCP calls or modify SQLite checkpoints. It writes to gitignored `outputs/writer_retries/` and keeps the original failed trace unchanged. Do not count retry as a separate independent task when computing completion rates. The prompt guidance does not replace scientific fact checking. No citations are ever auto-inserted into unsupported statements.

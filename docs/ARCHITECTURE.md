# 架构与数据流

## 1. 两种运行模式

**基础 Tool Calling Agent**：`research_agent.py` 使用 `MessagesState` + `ToolNode`，模型自主请求 `search_papers`、`ask_rag`；最多设置了 3 轮工具循环，并可做可选引用审计与科学主张初步标记。

**规划驱动 Agent（正式展示主入口）**：`planned_workflow.py` 以计划驱动工具执行，而不是让模型每一步直接发起任意工具调用。

```mermaid
flowchart TD
  Q[研究问题] --> P[Planner: JSON 计划 + 校验]
  P --> E[Executor: 取 plan[cursor]]
  E -->|search_papers / ask_rag| HTTP[外部 FastAPI /search /ask]
  E -->|analyze_csv| PY[pandas / matplotlib]
  E -->|mcp_analyze_csv| MCP[MCP Client stdio -> MCP Server]
  MCP --> PY
  HTTP --> V[Verifier: 工具状态、来源页码]
  PY --> V
  V -->|下一个工具步骤| E
  V -->|到 final_answer| W[Writer: 有证据的中文报告]
  W --> A[report + JSON trace]
  P -. checkpoint .-> DB[(SQLite Checkpointer)]
  E -. checkpoint .-> DB
  V -. checkpoint .-> DB
  W -. checkpoint .-> DB
```

## 2. 关键 State

`task` 任务文本；`plan` 结构化步骤；`cursor` 当前执行下标；`pending` 等待核验的本次工具结果；`records` 累积执行记录；`refs` 允许引用的论文页码；`issues` 风险；`answer` 报告；`status` 报告状态；`dataset_context` 数据集合法列名、SHA-256 与 backend。

Plan 不直接调用工具。Executor 从经过校验的 plan 中选择动作，Verifier 写入 `records`，在已完成步骤后生成检查点。Writer 使用受控证据和结果生成报告。`Status: SOURCES_LINKED_NOT_FACT_CHECKED` 的含义只是页码存在于检索结果中。

## 3. MCP 数据通路

`mcp_analysis_bridge.analyze_csv_via_mcp` → 官方 `mcp.Client`（本地子进程 stdio） → `mcp_server.MCPServer` → 受限 `data_analysis_tool.py` 子进程 → JSON 工具结果。只允许 `demo_gasification`、固定列和 `summary/correlation/scatter_plot` 三种操作。MCP 模式由 CLI `--mcp` 明确启用。

## 4. 恢复边界

`checkpoints/research_agent.sqlite` 存储 LangGraph thread 检查点。首次任务 `--thread-id`，暂停时 `--pause-after-step`；恢复用同一 ID 与 `--resume`，并从 `graph.invoke(None)` 继续。已完成并写入检查点的节点通常不会重新执行，但外部副作用在网络崩溃时不保证 exactly-once。

Writer 采用限制输入和生成长度的方式缓和 GLM 超时：论文证据 11,000 字符、CSV 4,000 字符、请求超时默认 180 秒、最多 1,600 tokens；曾有真实 156.7 秒 Writer 请求成功，非基准延迟。

## 5. 尚需改善

参考文献页过滤；证据句级验证；更明确的 `PAUSED` / `IN_PROGRESS` 状态映射；GLM 超时与工具失败的受控重试、幂等处理；真实科研数据来源管理；可复现的批量 Agent 评测。

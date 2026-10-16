# 技能清单、模块清单与代码对应关系

> 以本次上传的 `ResearchAgent.zip` 中源码为准；不把计划开发的功能写作已实现。

## A. 技能与证据

| 能力 | 使用的技术 | 代码证据 | 状态 |
|---|---|---|---|
| 大模型调用 | `langchain_openai.ChatOpenAI`，GLM 的 OpenAI 兼容接口 | `research_agent.py:create_model` | 已运行 |
| Function Calling | LangChain `@tool`、`bind_tools`、`ToolNode` | `research_agent.py` | 已运行（独立基础模式） |
| LangGraph 自定义工作流 | `StateGraph`、Node、Edge、条件路由 | `planned_workflow.py:build_workflow` | 已运行 |
| 结构化任务规划 | GLM 生成 JSON、`validate_plan` 白名单校验 | `planner.py` | 已运行 |
| RAG HTTP 工具 | `urllib.request` 请求 `/search`、`/ask` | `research_agent.py:search_papers/ask_rag` | 已运行，依赖独立服务 |
| 本地数据分析 | pandas、Pearson、matplotlib | `data_analysis_tool.py` | 已运行（演示数据） |
| MCP 协议与工具发现 | `MCPServer`、`Client`、stdio | `mcp_server.py`、`mcp_analysis_bridge.py` | 已运行 |
| 跨进程检查点 | `SqliteSaver`、`thread_id`、`graph.invoke(None)` | `planned_workflow.py`、`day3_checkpoint_demo.py` | 正常暂停/恢复已运行 |
| 引用来源核验 | 包装行 `(paperXX.pdf,p.N)` 提取与白名单 | `planned_workflow.py:source_refs/write_evidence_answer` | 已实现；非事实核验 |
| 初步主张审核 | 引文检索、启发式风险和可选模型自审 | `agent/`、`research_agent.py` | 基础模式中实现；不是主流程强制节点 |
| 错误处理与安全 | 文件路径限制、参数限制、工具异常状态 | `data_analysis_tool.py`、`planner.py`、`planned_workflow.py` | 部分实现 |

**Skills 的概念区别：** 这里的“技能”是模型和 Agent 的能力；源码中没有类似独立 `SKILL.md`、可安装技能包的 Agent Skills 系统，不应写成“已使用 Skills 框架”。同理，`MCP` 是协议集成，不能等同“Agent 可以连接任何外部服务”。

## B. 主流程模块

1. `planner.py`：生成可执行计划、限制 2～6 步并校验工具、数据集、操作和列名；必须包含 `search_papers`。
2. `planned_workflow.py`：Agent 主入口与 `WorkflowState`（`task`、`plan`、`cursor`、`pending`、`records`、`refs`、`issues`、`answer`、`status`、`dataset_context`）。节点：`planner` → `executor` → `verify_step` → `writer`，其中 `verify_step` 可返回 `executor`。
3. `research_agent.py`：独立基础 Agent；提供 `search_papers`、`ask_rag` HTTP 工具，并支持 `--audit`、`--review-claims`、`--judge`。主工作流重用其中的两个 RAG 工具及 `create_model()`。
4. `data_analysis_tool.py`：允许 `summary`、`correlation`、`scatter_plot`，并限制输入路径、文件大小、CSV 行列数及有效数据。
5. `mcp_server.py`：本地 MCP Server，有 `list_datasets`、`describe_dataset`、`analyze_demo_csv` 三个 MCP Tool。只支持人工演示数据集。
6. `mcp_analysis_bridge.py`：把同步 Executor 请求转换为 MCP stdio 客户端调用，并验证工具名、返回数据和图表路径。
7. `mcp_client_demo.py`：本地无 GLM 的 MCP 通信验证样例。
8. `day3_checkpoint_demo.py`：用 Mock 状态演示跨进程恢复；并不是正式 Agent 的运行入口。
9. `agent/citation_audit.py`：检查回答中引文能否匹配工具返回页码。
10. `agent/claim_evidence_review.py` 与 `agent/quality_gate.py`：初步科学主张抽取、风险标记与质量门槛；模型“支持”标签不能代替人工核对 PDF。

## C. 不应写进简历“已实现”的功能

- 多智能体团队（当前是一个工作流，多个节点不是多个独立 Agent）。
- 通用自由执行 Python 代码（当前只允许预定义 CSV 操作）。
- 通用互联网搜索、自动下载 SCI 论文（当前工具只调用已有本地 RAG 服务）。
- 长期向量记忆 / 个人知识 Store（现有 SQLite 保存的是线程执行状态）。
- 独立科学事实验证、论文定量结论可靠性保证。
- 可任意接入 MCP 生态工具（目前是受限本地 MCP 工具）。
- 系统化生产级 Task Success Rate 或大样本吞吐量评测（下一阶段计划）。

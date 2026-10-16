# ResearchAgent 最新整理记录（2026-10-16）

## 依据与原则

依据用户最新上传的 `ResearchAgent (2).zip` 静态逐文件审查。源包共有 **102 个 ZIP 条目（包含目录）**。整理包采用源文件白名单复制，**核心 Python 源码及相互导入路径不更改**。用户电脑的旧项目、本地 SQLite 和输出文件均不被本次操作删除或覆盖。

## 正式代码与入口

- **主入口**：`planned_workflow.py`（Planner → Executor → Verifier → Writer；RAG/MCP、SQLite、计时）
- **任务规划**：`planner.py`；**旧版工具调用 Agent 对照实现**：`research_agent.py`
- **工具**：`data_analysis_tool.py`、`mcp_server.py`、`mcp_analysis_bridge.py`
- **辅助诊断**：`mcp_client_demo.py`、`day3_checkpoint_demo.py`、`scripts/retry_writer.py`
- **审查/指标**：`agent/`、`evaluation/`；**自动测试**：`tests/`
- **公开演示数据**：`data/demo_gasification.csv`（合成数据，非真实科研实验）

保留所有 Day 1–Day 4 已迭代完成的正式模块，**不合并、重写或删除业务逻辑**。`docs/README_DAY4_TIMING.md` / `docs/README_WRITER_RETRY.md` 仅在发布包中改成较清楚的 `docs/NODE_TIMING.md` / `docs/WRITER_RETRY.md`（内容未改）。

## 从公开发布包排除，但可以本地存档

| 类别 | 最新源包中的代表文件 | 处理理由 |
| --- | --- | --- |
| 旧版本备份 | `planned_workflow_pre_timing.py`、`evaluation/trace_metrics_pre_timing.py` | 正式主模块已包含新版本，备份保存在原 ZIP 即可 |
| 运行数据 | `outputs/` 全部内容（报告、散点图、Writer 重试 JSON） | 可能含论文摘录、任务和模型输出，不应无审核上传 |
| 状态库 | `checkpoints/research_agent.sqlite` | LangGraph 持久化状态及原始上下文 |
| 原始评测输出 | `eval_outputs/` | 由本地记录再生；公开指标以 `docs/DAY4_RESULTS.md` 的审慎汇总为准 |
| 开发环境 | `__pycache__/`、`.vscode/` | 缓存和本机编辑器配置，不属于源码发布 |

源包未包含真实 `.env.agent`，发布包**只含 `.env.agent.example` 占位符模板**。仍须在 Git 暂存和推送前检查是否出现密钥、论文 PDF、私人路径、输出记录或历史提交。

## 测试范围（不要混淆）

- 可在当前整理环境直接运行的纯 Python 检查：源文件 `compile` 语法检查、`tests.test_day4_metrics`、`tests.test_day4_writer_retry`、`evaluation.trace_metrics` 对源包真实六条记录的统计。
- 当前整理环境缺少 `langgraph`、`langchain_openai` 和 `mcp`，**无法在这里验证完整工作流、MCP 通信和 SQLite 恢复**。用户此前在 Windows `thermowaste-agent` 环境中的测试输出已通过；发布包还应在用户本机再次验证。
- GitHub 公开包不含 `.git/`：若在本机提示 `fatal: not a git repository`，表示该目录**尚未初始化版本库**，不是 ResearchAgent 代码错误。按 `docs/GITHUB_RELEASE_STEPS.md` 检查后初始化。

## 替换建议

优先将整理 ZIP 解压到新目录审阅；若用户要继续使用 `D:\ResearchAgent` 路径，应先把旧目录重命名为例如 `D:\ResearchAgent-local-backup`。之后只在新目录中初始化 Git，使用 `.gitignore` 验证待提交内容，不要直接上传整个原始 ZIP。

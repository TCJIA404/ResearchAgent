# 运行与测试指南（Windows / Conda）

## 环境

```cmd
conda activate thermowaste-agent
cd /d D:\ResearchAgent
python -m pip install -r requirements.txt
python -m pip check
```

将 `.env.agent.example` 复制为不纳入 Git 的 `.env.agent`，填写大模型 API Key、Base URL、模型名称。`RAG_API_URL` 默认为 `http://127.0.0.1:8000`。需要先在独立 ThermoWaste-RAG 项目启动 FastAPI；`GET /health` 正常后再运行文献任务。

## A. 基础 ToolNode Agent

```cmd
python research_agent.py --question "How does gasification temperature affect hydrogen production?" --audit
python research_agent.py --question "How does steam/fuel ratio affect H2?" --review-claims --save
```

## B. 主规划工作流

```cmd
python -u planned_workflow.py --task "How does gasification temperature affect hydrogen production?" --save
python -u planned_workflow.py --task "Compare literature and demo data, calculate temperature/H2 correlation and draw a scatter plot" --dataset demo_gasification --mcp --thread-id research_101 --pause-after-step
python planned_workflow.py --status --thread-id research_101
python -u planned_workflow.py --resume --thread-id research_101 --save
```

恢复任务不要再次提供 `--task`、`--mcp`、`--dataset`；不要复用其他已存在的线程 ID。第一次执行若希望不断点直接跑完，可以不加 `--pause-after-step`。

## C. 不使用 GLM 的离线/本地测试

```cmd
python -m tests.test_research_agent
python -m tests.test_planner
python -m tests.test_planned_workflow
python -m tests.test_data_analysis_tool
python -m tests.test_day2_integrated_workflow
python -m tests.test_day3_checkpoint
python -m tests.test_day3_real_checkpoint
python -m tests.test_day3_mcp_agent
python mcp_client_demo.py
```

部分离线测试会启动本地子进程并创建临时 PNG/SQLite，但不需要外部 GLM。基础测试在用户的 `thermowaste-agent` 环境中此前已通过。本整理包的执行环境未安装 LangGraph/MCP，因此只完成代码静态检查；发布前请在用户本地重新运行全部测试。

## D. 数据分析工具单独验证

```cmd
python data_analysis_tool.py --dataset demo_gasification --operation summary
python data_analysis_tool.py --dataset demo_gasification --operation correlation --x temperature_C --y hydrogen_vol_pct
python data_analysis_tool.py --dataset demo_gasification --operation scatter_plot --x temperature_C --y hydrogen_vol_pct --save
```

演示 CSV 的 16 行数据是 synthetic，运行时 `r≈0.875545` 属于可复核的软件功能，不是科学结论。

## E. 常见问题

- `GET /` 为 404：FastAPI 没有定义根主页；测试 `/health` 或 `/docs`。
- `ValueError`：可能为计划校验、非法数据集或已存在 `thread_id`；先执行 `--status`、使用新线程，不要删除数据库。
- `OpenAITimeoutError`：上游 GLM/Writer 请求超时；已提交检查点可用同 ID 继续，但不应无限重试。
- `status: NOT_STARTED` 且 `completed_steps > 0`：状态展示字段尚未细分；以 `next_nodes`、`completed_steps` 判断是否部分完成。
- `SOURCES_LINKED_NOT_FACT_CHECKED`：仅说明引用指向本次检索得到的页码，不代表科研内容被验证。
- 不能复现 PDF 问答：需要自行合法准备论文语料，并启动独立 RAG API；本仓库不包含原始 PDF 或索引。

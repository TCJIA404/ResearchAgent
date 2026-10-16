# Day 4 · ResearchAgent Evaluation (评测及故障注入)

## 范围

这套工具是对现有 **Day 1–3 已验收工作流** 的补充；**不覆盖** `planner.py`、`planned_workflow.py`、`research_agent.py`、MCP 或 SQLite 核心源码。

新增模块：

- `evaluation/trace_metrics.py`：读取 `outputs/planned_agent_*.json`，评估可观察的记录完整度、工具返回状态、引用页码匹配及模拟数据声明；生成不含文献摘录的汇总表。
- `tests/test_day4_metrics.py`：离线指标计算检查（标准库，无 API 请求）。
- `tests/test_day4_fault_injection.py`：向真实 `build_workflow()` 注入模拟 RAG 故障、MCP 故障与 Writer 超时，并校验 SQLite 恢复（需要现有 LangGraph/SQLite 依赖，但不请求真实 GLM/RAG）。

## 1. 运行指标单元测试

在 `D:\ResearchAgent` 中：

```cmd
conda activate thermowaste-agent
cd /d D:\ResearchAgent
python -m tests.test_day4_metrics
```

## 2. 评估已有真实执行记录（离线、无 Token 消耗）

```cmd
python -m evaluation.trace_metrics --input outputs --output-dir eval_outputs
```

整理版原本**不包含**旧 `outputs/`；若目录不存在或为空，应从自己本地备份目录中只复制 `planned_agent_*.json`，或直接指定旧目录：

```cmd
python -m evaluation.trace_metrics --input "D:\旧项目备份目录\outputs" --output-dir eval_outputs
```

其中 `D:\旧项目备份目录` 是示意路径，请换成**实际**的旧目录。

将生成：

```text
eval_outputs/day4_metrics.json
eval_outputs/day4_report.md
```

请不要将旧原始完整 traces、`outputs/`、`checkpoints/`、`.env.agent` 或未授权 PDF 上传 GitHub。

## 3. 模拟故障，验证错误隔离和恢复

```cmd
python -m tests.test_day4_fault_injection
```

预期检验：

1. RAG API 不可用（模拟 ConnectionError）→ 记录 `TOOL_ERROR`，无有效来源时不生成虚构科研结论。
2. MCP 分析失败（模拟 RuntimeError）→ 若文献证据存在，允许生成明确标注失败分析步骤的部分报告。
3. Writer 超时（模拟 TimeoutError）→ 重开 SQLite 检查点，继续执行 Writer；已完成的 Planner 和 Search 不重复。

> 模拟故障成功，不等于真实网络中间故障的恢复成功率，也不能保证 MCP 服务具备严格的 exactly-once 语义。

## 指标定义（必须谨慎命名）

- `completed_report_rate`：已保存且执行步骤与计划一致、具有报告和可识别结束状态的 **trace 比例**；不等于实际用户任务的正确完成率。
- `tool_call_nonerror_rate`：已记录的工具调用中非 `TOOL_ERROR` 比例；`NO_EVIDENCE` 属于无异常、但未检出证据，需要单独衡量。
- `search_evidence_rate`：`EVIDENCE_FOUND / search_papers` 的比例。
- `answer_citation_page_match_rate`：报告引用的不同 paper/page 在已保存检索来源集合中的占比；不代表引用的内容确实支持论点。
- `synthetic_trace_label_rate`：含人工模拟 CSV 工具结果的 trace 中，回答明确标识合成 / 模拟数据的比例。
- `resume_success_rate`：**现有 JSON 无恢复尝试记录，无法计算**。必须后续增加恢复尝试分母和成功/失败事件。
- `Planner/Executor/Writer latency`：**现有 JSON 无节点持续时间，无法从中计算**。不要把一次已知 Writer 156.7 秒的终端日志当成所有运行的平均延迟。
- `task_success_rate`：需要独立定义任务验收条件并人工/程序标注，当前只计算 **最终报告完成率**。

## 对旧运行记录的解读

在此前上传的项目归档中，可见 4 条完成的 `planned_agent_*.json`。它们属于挑选保留的成功样例，不包括失败的 GLM 超时尝试。因此不应该说“生产任务成功率 100%”，只能说明这些**已保存成功记录**的完成情况。

## 下一步（Day 4 后半段）

1. 给 LangGraph 节点加入单调时钟耗时记录，Writer 同时记录请求和响应长度，注意不要记录 Key 和完整 prompt。
2. 新增面向固定任务集的成功/失败标签，包含超时和未保存的尝试记录，统计有完整分母的成功率。
3. 选择 3–5 个 Badcase，由人工对照真正 PDF 内容进行引用事实核验；`SOURCES_LINKED_NOT_FACT_CHECKED` 必须保留。

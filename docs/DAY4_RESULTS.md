# Day 4：运行评测与可靠性案例（基于 2026-10-12 的本地记录）

> 该文档是有限的开发测试观察，不是生产性能基准，也不是科学事实核验。汇总依据为最新上传包中的 6 份 `outputs/planned_agent_*.json`，原始 JSON、PDF 内容和 SQLite 状态**不公开分发**。

## 1. 保存记录汇总（6 份，不等于全部尝试）

| 指标 | 观察结果 | 解释与限制 |
| --- | ---: | --- |
| 已保存执行记录 | 6 | 4 份完成、2 份受阻；未保存的超时尝试不在内 |
| 已生成合格完整报告 | 4/6 (66.7%) | 只是保存样本内报告完成率，不是整体任务成功率 |
| 工具调用无执行错误 | 17/18 (94.4%) | 不是“业务操作成功率”或科研结论正确率 |
| 检索返回论文来源页码 | 8/9 (88.9%) | 检索源标识可用，不等于证据质量达标 |
| 已完成报告的引用页码匹配 | 100% | 仅匹配 `(paperXX.pdf, p.N)` 标识，不验证引文是否支持论断 |
| 可统计的节点计时记录 | 2/6 | 其他 4 份没有计时字段，不应补造 |
| 端到端科研任务成功率、恢复成功率、Token 成本 | 未测量 | 缺乏涵盖所有尝试的分母、事件日志或用量 |

最初只审计四份成功运行记录时，看到 **4/4 报告完成、12/12 工具调用无错误**；加入两份真实失败案例后更完整的口径如上。不可把初期 100% 当成独立无偏成功率。两份已完成的合成数据报告均明确标注 `SYNTHETIC DEMONSTRATION DATA`；受阻报告的合成数据标注不能当作已发布成果。

## 2. 真实故障与局部重试

| 任务 | 真实现象 | 最终状态 | 价值 |
| --- | --- | --- | --- |
| `timing_mcp_001` | RAG FastAPI 未启动；MCP 数据分析成功 | `NO_EVIDENCE` | 拒绝凭模拟数据编造文献结论 |
| `timing_mcp_002` | RAG 检索及 MCP 成功，但 GLM 草稿没有合规论文页码引用 | `BLOCKED_UNCITED_ANSWER` | 引用质量门禁拒绝发布 |
| Writer-only retry | 读取 `timing_mcp_002` 保存的检索/分析证据，只重试 GLM Writer | `SOURCES_LINKED_NOT_FACT_CHECKED` | 保留原始失败记录，避免重复检索和 MCP 计算 |

**Writer-only retry 不是新的独立 Agent 任务**，也不会将原来的失败记录改写为成功。页面引用通过并不代表句子内容已获原文证实。

## 3. 节点耗时（两条记录，非总体均值基准）

| 项目 | Planner | Executor | Verifier | Writer |
| --- | ---: | ---: | ---: | ---: |
| `timing_mcp_001`（RAG 离线） | 8936.149 ms | 7605.597 ms | 0.017 ms | 0.075 ms |
| `timing_mcp_002`（引用不合格） | 14387.863 ms | 6177.646 ms | 0.059 ms | 61430.104 ms |

计时为已完成节点耗时累计（Executor 可多次执行），**不是端到端墙钟时长**，不含网络超时后进程重启间隙或失败节点尝试。Writer 独立重试耗时约 32.1 秒，与首次约 61.4 秒为不同请求，不能当作可靠加速结论。

## 4. 离线故障注入（模拟，不消耗真实 GLM API）

- RAG 断连：`TOOL_ERROR`，无文献来源时 `NO_EVIDENCE`；不编造出处。
- MCP Server 失败：在仍有检索证据时生成带失败声明的受限部分报告。
- Writer 超时：借助 LangGraph SQLite 已提交检查点恢复，不重复已提交的 Planner/Search；**不保证任意崩溃点的 exactly-once**。
- 引用门禁：缺失页码或未检索来源页码的草稿被拦截。

## 5. 如何自己复现指标

```cmd
python -m tests.test_day4_metrics
python -m tests.test_day4_fault_injection
python -m tests.test_day4_timing
python -m tests.test_day4_writer_retry
python -m evaluation.trace_metrics --input outputs --output-dir eval_outputs
```

最后一条需要用户**本地保存的任务记录**，干净 GitHub 包默认不包含 `outputs/`。若未找到记录，请查看 `docs/RUNBOOK.md` 先用本地 RAG/GLM 或模拟测试完成验证。指标不能替代逐条科学事实核验。

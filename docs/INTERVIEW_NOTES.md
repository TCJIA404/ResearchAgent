# ResearchAgent · 秋招面试讲解与简历素材

## 一句话介绍

基于 LangGraph 实现规划—执行—核验—写作的科研分析 Agent，融合文献 RAG API、MCP 工具调用和受限 CSV 计算，并通过 SQLite 持久化执行状态；引入来源页码门禁、故障注入和局部 Writer 重试来降低无依据输出及重复执行风险。

## 模块为什么这样设计

- **Planner：** 大模型生成 JSON 计划，但由白名单与列名校验决定可执行范围。
- **Executor：** 执行文献检索与受限数据计算；直接 Python tool 与真正的 MCP stdio Client/Server 两种路径，便于比较。
- **Verifier：** 检查工具状态、来源引用；注意页码匹配不是事实核验。
- **Writer：** 汇总各工具输出，必须按已获检索来源书写，否则阻止发布。
- **SQLite：** `thread_id` 支持从已提交节点恢复；不承诺所有中途故障 exactly-once。
- **Evaluation：** 统计已保存 Trace 的成功/失败状态、引用页码以及节点耗时，离线做故障注入。

## 可讲的两个真实 Badcase

**问题 1：RAG API 忘记启动。** Planner 和 MCP 仍可运行，但文献检索 `TOOL_ERROR`，状态 `NO_EVIDENCE`，Agent 不输出无证据的科研结论。体现错误隔离与降级；不能声称生产环境自动修复服务。

**问题 2：Writer 没给页码引用。** RAG/MCP 已成功，但 Writer 草稿被引用门禁标记 `BLOCKED_UNCITED_ANSWER`。独立重试工具复用既有 JSON 证据，只再次调用 GLM Writer，得到 `SOURCES_LINKED_NOT_FACT_CHECKED`，原失败记录不变。体现局部重试与审计追溯；仍未做逐句科学事实验证。

## 简历项目描述（可据实际改写）

**ResearchAgent｜科研多工具智能体（Python / LangGraph / MCP / SQLite / GLM）**

- 设计 Planner–Executor–Verifier–Writer 多节点任务工作流，支持结构化计划验证、RAG 文献检索、MCP 工具调用及受控 CSV 分析。
- 基于 LangGraph SQLite Checkpointer 实现任务暂停与恢复；通过故障注入验证 RAG 异常、MCP 分析失败和 Writer 超时的受控处理。
- 建立来源页码检查与执行记录评测工具；在 4 份已保存完整记录中观测到 12/12 次工具调用未记录执行错误，并保留真实引用失败与 Writer 单独重试案例。

## 需要能回答的追问

1. `ToolNode` 自由选择工具与 plan-based Agent 有什么不同？为什么展示版本选后者？
2. MCP 与直接 Python 函数调用有什么区别？实际是否走 stdio 协议？
3. SQLite checkpoint 存的是节点状态还是长期语义记忆？中断时哪些操作可能重复？
4. Why `SOURCES_LINKED_NOT_FACT_CHECKED`? 论文引用形式与论断证据支持分别如何验证？
5. 为什么 12/12 非错误工具调用不能解释为任务成功率 100%？
6. Writer 超时时如何处理？局部重试与 LangGraph checkpoint resume 有何不同？
7. 对于 16 行人工合成数据，Pearson r 说明什么，不能说明什么？

## 不要夸大的点

不要写“自主科研发现”“科研事实验证”“所有异常自动恢复”“生产级 100% 成功率”或“端到端零成本”，因为现有测试不支持这些结论。

# Day 5：ResearchAgent GitHub 发布步骤（Windows）

## 一、发布范围

**发布：** `planned_workflow.py`、`planner.py`、RAG/MCP/CSV 适配器、`agent/`、`evaluation/`、`scripts/`、`tests/`、可公开的合成 CSV、README 和 docs。

**不要发布：** `.env.agent` 或真实 API Key，`outputs/` 中含论文摘录的运行记录，`checkpoints/` SQLite 数据库，`eval_outputs/` 的未经审查报告，论文 PDF、FAISS 索引、开发阶段备份、旧 ZIP。

独立 RAG 服务依赖需要另行启动，ResearchAgent 仓库**不是拿到源码即可离线得到真实论文回答**。它的合成 CSV 演示与离线测试才是不要求文献数据的复现部分。

## 二、在本机检查（不调用 GLM）

```cmd
conda activate thermowaste-agent
cd /d D:\ResearchAgent
python -m tests.test_planner
python -m tests.test_data_analysis_tool
python -m tests.test_day3_real_checkpoint
python -m tests.test_day3_mcp_agent
python -m tests.test_day4_metrics
python -m tests.test_day4_fault_injection
python -m tests.test_day4_timing
python -m tests.test_day4_writer_retry
```

如果某个测试缺文件或失败，先修复后再发布；不要在 README 声称未执行的测试已通过。

## 三、先查看是否已有 Git 仓库

```cmd
git status
git remote -v
```

如果显示不是 Git 仓库，再运行：

```cmd
git init -b main
```

执行下面命令先检查即将纳入 Git 的文件：

```cmd
git add .
git status --short
git diff --cached --name-only
```

**停止并人工检查待提交列表**：确保不出现 `.env.agent`、`outputs/`、`eval_outputs/`、`checkpoints/`、PDF、SQLite、旧备份和 ZIP。若有误加入，使用 `git restore --staged "文件路径"` 暂存区移除，必要时完善 `.gitignore`。仅 `git status --short` 看不到文件内容，至少打开 README/示例配置/代码中的硬编码配置进行检查；已经提交过密钥则单纯新增 `.gitignore` 无法删除历史泄漏，必须先轮换密钥并修复历史。

没有敏感信息后：

```cmd
git commit -m "Release ResearchAgent with MCP, checkpointing and evaluation"
```

## 四、创建远程 GitHub 仓库并推送

在 GitHub 网站创建一个**空的公开仓库**，推荐名称 `ResearchAgent`，创建时不要勾选自动生成 README 或 `.gitignore`。用页面实际给你的 HTTPS 地址替换下面的 URL（这里仅是模板）：

```cmd
git branch -M main
git remote add origin https://github.com/你的用户名/ResearchAgent.git
git push -u origin main
```

如果 `git remote -v` 已经有 `origin`，不要再执行 `git remote add origin`，应先确认远程仓库是否正确。GitHub 网页登录并不等于 Git 命令行已配置认证；如弹出认证窗口，使用 Git Credential Manager 的正常流程。

## 五、发布后验收

1. GitHub 首页能正确显示中文 README 和 Mermaid 流程图。
2. Python 源码、`requirements.txt`、`data/demo_gasification.csv`、离线测试与 Day 4 评测说明可见。
3. GitHub 网页中**没有**密钥、论文全文、原始运行记录、旧备份或 SQLite。
4. README 明确说出独立 RAG API 前置依赖，以及合成数据/引用真实性边界。
5. 从一个全新本地目录克隆后，基础的离线测试能够正常安装并运行（最好再执行一次；完成前不要承诺已复现）。

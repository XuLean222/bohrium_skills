# Xuling Skills Collection

本目录包含 4 个 Claude Code Skills，用于数据查询、分类、评测和反馈追踪。

## Skills 列表

### 1. [sn-search-runner](./sn-search-runner/)

**功能**：运行 Science Navigator (SN) AI 搜索，自动进行 AI 评分，并将结果写入飞书多维表格。

**适用场景**：
- 批量运行 SN 搜索查询
- 自动评测搜索质量（15 个维度 + 满分/扣分理由）
- 获取 LLM trace 信息（通过 Opik）
- 结果自动写入飞书多维表格

**主要特性**：
- 支持 CSV/JSON/XLSX 三种输入格式
- 多线程并发执行
- 自动去重
- 批次管理（task_id）
- prod 环境 URL 已修复（`www.bohrium.com`）

**使用方式**：
```bash
cd sn-search-runner

# 方式一：使用 batch_run.py 批量搜索 + AI 评分 + 写入飞书多维表格
# 先在 scripts/const.py 中填入 SN_TOKEN、LARK_APP_TOKEN、LARK_TABLE_ID、DIFY_API_KEY
python3 batch_run.py

# 方式二：使用 run_search.py 单条/批量查询
cd scripts
python3 run_search.py "查询内容"  # 单条查询
python3 run_search.py              # 批量查询（从配置文件读取）
```

**配置说明**：
在 `scripts/const.py` 中填入以下配置：
```python
SN_TOKEN = ""         # Bohrium API Token（从浏览器 DevTools 获取）
LARK_APP_TOKEN = ""   # 飞书多维表格 app_token
LARK_TABLE_ID = ""    # 飞书数据表 table_id
DIFY_API_KEY = ""     # Dify 评分工作流 API Key
```

---

### 2. [sn-query-classification](./sn-query-classification-skill/)

**功能**：对包含 query 列的 Excel 文件进行 LLM 分类，输出能力类别、学科领域、意图动作等分类结果。

**适用场景**：
- Query 能力分类（搜索/问答/推荐等）
- 学科领域分类（自然科学/工程技术/生命科学等）
- 意图分类（主意图/隐含意图/动作/限制条件）

**主要特性**：
- 三阶段分类流水线（能力 → 学科领域 → 意图）
- 基于 Azure OpenAI
- 并行处理
- 输出合并到同一张表

**使用方式**：
```bash
cd sn-query-classification-skill
python scripts/run_all_classifications.py --input queries.xlsx --output results.xlsx
```

---

### 3. [link_dms_skill_for_claude_code](./link_dms_skill_for_claude_code/)

**功能**：通过阿里云 CLI 查询 DMS 数据库 SQL 并导出数据，无需打开 DMS 控制台。

**适用场景**：
- 执行预置 SQL 查询场景（14 个预置场景）
- 即时 SQL 查询（ExecuteScript）
- 大结果集导出（创建导出工单）
- 查询 SN 用户提问、反馈、统计数据等

**主要特性**：
- 14 个预置查询场景
- 支持即时查询和导出工单两种模式
- 自动解析 DbId
- 固定张家口地域配置

**使用方式**：
```bash
cd link_dms_skill_for_claude_code
./scripts/dms_query.sh --list-scenarios  # 列出所有场景
./scripts/dms_query.sh --scenario 11     # 执行场景 11
./scripts/dms_query.sh --scenario 9 --export  # 创建导出工单
```

---

### 4. [sn-feedback-tracker](./sn-feedback-tracker/)

**功能**：AI 小导师反馈自动追踪系统，查询点踩和评分数据，Claude 访问原始会话归因问题，写入飞书多维表格。

**目标表格**：https://dptechnology.feishu.cn/base/FQlvbn8yxaBOsPsVKsncPCA6nqc

**完整工作流**：
1. 从 DMS 查询点踩（`reaction_type=2`）和评分（`scholar_QA`）数据
2. 拼接会话分享链接：
   - 点踩：`https://www.bohrium.com/chat/share/{URL最后一段}?qid={session_id}`
   - 评分：`https://www.bohrium.com/chat/share/{conversation_id}?qid={session_id}`
3. Claude 调用 `/bohrapi/v1/sigma-search/api/v4/{session_id}/history` 读取会话内容（token 在 `/tmp/bohrium_token.txt`），结合用户反馈原因归因
4. 批量写入飞书多维表格，处理人由用户手动 @

**问题层面归因**（关键，与直觉不同）：
- **产品层面**：仅用户的新功能需求 / 迭代建议
- **研发层面**：AI 回答质量（截断、幻觉、引注不足/陈旧、意图偏差）、功能异常、报错、性能 —— **绝大多数反馈都属于此类**
- **设计层面**：UI 显示、样式、视觉

**优先级规则**（已结合归因实践沉淀）：
- P0：系统异常（截断/空壳）、编造事实（幻觉）、核心功能不可用
- P1：功能异常、文献不全、低质量论文（意图偏差）
- P2：文献陈旧、语言不匹配、UI 细节

**使用方式**：
```bash
cd sn-feedback-tracker

# 按日期查询
./scripts/track_feedback.sh --date yesterday
./scripts/track_feedback.sh --date 2026-04-19 --type dislike  # 仅点踩
./scripts/track_feedback.sh --date today --dry-run            # 预览

# 自定义时间窗（小时级）
./scripts/track_feedback.sh \
  --start-time "2026-04-23 17:00:00" \
  --end-time   "2026-04-24 17:00:00"
```

**自动化运行**：
```bash
# crontab：每天 9 点跑昨天
0 9 * * * cd /path/to/xuling/sn-feedback-tracker && ./scripts/track_feedback.sh --date yesterday

# 或在 Claude Code 内：
/loop 1d 查昨天的小导师反馈并归因写入飞书
```

**已知限制**：
- 会话访问需 `/tmp/bohrium_token.txt` 内的 Bearer token 有效；过期需重新抓取
- 单日反馈 > 50 条时建议分批
- 当前去重仅按 URL，未做相似度匹配

---

## 配置要求

| Skill | 依赖 | 配置项 |
|-------|------|--------|
| sn-search-runner | Python 3, requests, openpyxl, opik, lark-cli | Bohrium Token, Dify API Key, 飞书 App Token |
| sn-query-classification | Python 3, openai, pandas, openpyxl | Azure OpenAI API Key & Endpoint |
| link_dms_skill_for_claude_code | 阿里云 CLI, jq | 阿里云 AccessKey (通过 `aliyun configure` 配置) |
| sn-feedback-tracker | 阿里云 CLI, lark-cli, jq, Python 3 | 阿里云 AccessKey + 飞书认证 (`lark-cli auth login`) |
# xuling 项目记忆

## sn-feedback-tracker Skill

AI 小导师（Science Navigator / Scholar QA）反馈追踪系统。

**位置**：`xuling/sn-feedback-tracker/`

### 目标表格

- Base Token: `FQlvbn8yxaBOsPsVKsncPCA6nqc`
- Table ID: `tblUegIr5F3D7iXa`
- URL: https://dptechnology.feishu.cn/base/FQlvbn8yxaBOsPsVKsncPCA6nqc

### 数据源

**点踩数据**（scene=`science_navigator`, reaction_type=2）：
- 表：`account_center.common_feed_back_log`
- 关键字段：`URL`、`session_id`、`feed_back_remark`（点踩原因）、`create_time`
- URL 拼接：`https://www.bohrium.com/chat/share/{URL字段最后一段}?qid={session_id}`

**评分数据**（scene=`scholar_QA`, session_id LIKE `adk_a_%`）：
- 表：`account_center.user_behavior_record` JOIN `sigma-search.hot_session`
- 关键字段：`conversation_id`、`session_id`、`target`（评分 0-10）、`remarks`（评分原因）、`create_time`
- URL 拼接：`https://www.bohrium.com/chat/share/{conversation_id}?qid={session_id}`

### 工作流

1. `scripts/track_feedback.sh --date yesterday [--type dislike|rating|all] [--dry-run]`
   - 查询 DMS，输出结构化 JSON（含 url、feedback_reason、rating_score、create_time、raw）
2. Claude 归因：访问会话 URL（WebFetch）+ 参考 feedback_reason + rating_score，判断：
   - 问题层面（多选）：产品层面 / 研发层面 / 设计层面
   - 优先级：P0 / P1 / P2
   - 问题描述（以用户反馈原因为主）
3. `scripts/write_to_bitable.py` 从 stdin 读 JSON，批量写入飞书

### 飞书字段映射

| 字段 | 来源 |
|------|------|
| url | 拼接的 share URL |
| 问题描述 | 用户的反馈原因（feed_back_remark / remarks） |
| 问题层面 | Claude 归因（多选） |
| 处理进度 | 留空（由处理人手动更新） |
| 优先级 | Claude 归因（P0/P1/P2） |
| 创建时间 | 反馈 create_time |
| 备注 | 原始数据 JSON |
| 处理人 | 用户在飞书手动 @ |

### 已知问题与约定

- **DMS 查询**：依赖 `aliyun` CLI（已安装在 `/Users/dp/.local/bin/aliyun`），`dms_query.sh` 返回 `.Results[0].{ColumnNames, Rows}`，Rows 是对象数组（字段名为 key），不是二维数组。
- **WebFetch 访问 bohrium share 页**：页面是 SPA，直接抓 HTML 拿不到对话内容。
- **读取会话内容的正确方式**：调用 `https://www.bohrium.com/bohrapi/v1/sigma-search/api/v4/{session_id}/history`，需带 Bearer token（已保存在 `/tmp/bohrium_token.txt`）。响应结构：`.data.historyData[]`，每条含 `channel.uiInfo.{type,subType,content}`。提取对话文本的路径：`select(.channel.uiInfo.subType == "@bohrium-chat/common/markdown") | .channel.uiInfo.content.text`——第 0 条为用户问题，第 1 条为 AI 回答。
- **归因规则**（已结合会话内容验证）：
  - "系统异常"：回答截断/空壳/结构不完整 → 研发层面 P0；历史完整但用户当时中断 → 研发层面 P1
  - "编造事实"：引注幻觉、内容不实 → 研发层面 P0
  - "文献不全"：引注数量低于用户要求 → 研发层面 P1
  - "文献陈旧"：引注年份偏老 → 研发层面 P2
  - "低质量论文"：意图理解偏差、AI 未按用户期望响应 → 研发层面 P1
  - "论文语言不匹配"：语体/语域不一致 → 研发层面 P2
- **问题层面定义**（重要，与直觉不同）：
  - **产品层面**：仅包括用户的**新功能需求**、**产品迭代建议**（例如"希望能导出 PDF"、"希望加一个对比功能"）。**不包括**现有功能/回答质量问题。
  - **研发层面**：AI 回答质量问题（截断、幻觉、引注不足/陈旧、语言不匹配、意图理解偏差）、功能异常、报错、性能问题——**绝大多数反馈都属于此类**。
  - **设计层面**：UI 显示、样式、视觉、排版问题。
- **已弃用"数据层面"**：召回/文献相关问题统一归入研发层面。
- **处理人分配**：不自动 @，写入后由用户在飞书手动分配。

### 历史运行记录

- 2026-04-22 处理了 2026-04-21 的 8 条点踩数据，全部写入成功。涉及 3 个会话。

## 依赖工具

- `aliyun` CLI（已配置凭证）
- `lark-cli`（已 `auth login`）
- `jq`
- Python 3
- 共享脚本：`xuling/link_dms_skill_for_claude_code/scripts/dms_query.sh`
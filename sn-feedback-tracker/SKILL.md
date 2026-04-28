---
name: sn-feedback-tracker
description: AI小导师反馈追踪：查询点踩和评分数据，访问原始会话归因问题层面/优先级/问题描述，写入飞书多维表格。适用于"小导师反馈"、"点踩数据归因"、"评分问题追踪"等场景。
---

# AI 小导师反馈追踪

> 完整使用文档、数据源 SQL、字段映射、FAQ 见同目录 [README.md](./README.md)。

## 触发场景

用户说以下话时调用本 Skill：
- 「查昨天/今天/某天的小导师反馈」
- 「把点踩数据归因后写入飞书」
- 「运行反馈追踪」
- 「跑下 yesterday 17:00 - today 17:00 的反馈」

## 编排步骤

1. **查询数据**：运行 `bash scripts/track_feedback.sh` —— 默认 `--date yesterday`，时间窗口可用 `--start-time '<DT>' --end-time '<DT>'` 自定义；输出会保存到 `/tmp/sn_feedback_items_*.json`。

2. **读取会话内容**（用于归因）：对每个 session_id（dislike 用 `session_id`，rating 用 `conversation_id`），调用：
   ```bash
   curl -sS "https://www.bohrium.com/bohrapi/v1/sigma-search/api/v4/{session_id}/history" \
     -H "authorization: Bearer $(cat /tmp/bohrium_token.txt)"
   ```
   返回 `.data.historyData[]`，提取对话文本：`select(.channel.uiInfo.subType == "@bohrium-chat/common/markdown") | .channel.uiInfo.content.text`，第 0 条为用户问题，第 1 条为 AI 回答。
   
   如果 token 过期（code != 0），降级仅用 `feed_back_remark` / `remarks` 归因，并提示用户更新 token。

3. **归因**（每条反馈）：结合**用户反馈原因 + 会话内容**判断三项：

   **问题层面**（多选，绝大多数归研发层面）：
   | 层面 | 适用场景 |
   |---|---|
   | 产品层面 | **仅**新功能需求/迭代建议（"希望加 X 功能"）。**不**包括回答质量问题 |
   | 研发层面 | AI 回答质量（截断、幻觉、引注问题、意图偏差、语言不匹配）、报错、性能 |
   | 设计层面 | UI/样式/视觉/排版问题 |

   **优先级**（单选）：
   | 优先级 | 标准 |
   |---|---|
   | P0 | 回答截断不可用、严重幻觉/编造事实、极低评分（≤2分） |
   | P1 | 回答质量明显偏差、点踩且指向明确问题、意图理解失败 |
   | P2 | 体验优化、评分中等（5-7）、文献陈旧、风格问题 |

   **问题描述**：以用户反馈原因为主，结合会话内容补充具体证据（如"引注 12 篇但表述与原文不符"、"回答在 4.1 节处截断"）。

4. **写入飞书**：构造 JSON（字段：`url` / `categories` / `priority` / `description` / `create_time` / `raw_data`），管道送入 `python3 scripts/write_to_bitable.py`。**不**写入「处理进度」字段（留空由人工更新）。

5. **报告用户**：输出时间窗、点踩/评分数量、各优先级分布；提示需要在飞书手动 @ 处理人。

## 关键约定

- 默认问题层面归为 **研发层面**，除非反馈明确是产品迭代诉求
- 「处理进度」字段留空，不写入默认值
- 问题描述要带具体证据（来自会话内容），不要只复述 feedback_reason
- 目标飞书表：`base-token=FQlvbn8yxaBOsPsVKsncPCA6nqc`、`table-id=tblUegIr5F3D7iXa`

## 关键脚本

- `scripts/track_feedback.sh` — 查询 DMS + 准备数据
- `scripts/write_to_bitable.py` — 接收归因 JSON 并写入飞书
- 共享 DMS 查询：`../link_dms_skill_for_claude_code/scripts/dms_query.sh`

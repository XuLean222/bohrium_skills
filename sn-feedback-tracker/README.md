# AI小导师反馈追踪系统

自动化追踪 AI 小导师的用户反馈（点踩、评分），Claude 自动归因并写入飞书多维表格。

## 快速开始

### 手动运行

```bash
# 查询昨天的反馈
./scripts/track_feedback.sh --date yesterday

# 查询指定日期
./scripts/track_feedback.sh --date 2026-04-19

# 只查询点踩
./scripts/track_feedback.sh --date yesterday --type dislike

# 只查询评分
./scripts/track_feedback.sh --date yesterday --type rating

# 预览模式（不写入飞书）
./scripts/track_feedback.sh --date yesterday --dry-run
```

### 在 Claude 对话中使用

直接告诉 Claude：

```
查昨天的小导师反馈
```

或

```
把 4 月 19 日的点踩数据归因后写入飞书
```

Claude 会自动：
1. 执行 DMS 查询
2. 拼接会话分享链接
3. 逐个访问会话页面
4. 阅读对话内容并判断问题层面
5. 生成问题描述
6. 写入飞书多维表格

**注意**：写入后需要在飞书表格中手动 @ 处理人。

## 工作流程

```
┌─────────────────┐
│ 1. DMS 查询     │  查询点踩和评分数据
│    - 点踩数据   │  (common_feed_back_log)
│    - 评分数据   │  (user_behavior_record)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. 拼接 URL     │  根据数据源不同使用不同规则
│    - 点踩: URL  │  提取最后一段
│    - 评分: conv │  conversation_id
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. Claude 归因  │  访问会话页面，阅读内容
│    - 访问会话   │  判断问题层面：
│    - 阅读对话   │  • 产品层面
│    - 判断层面   │  • 研发层面
│    - 生成描述   │  • 设计层面
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. 写入飞书     │  批量写入多维表格
│    - 构造记录   │  (每批最多 200 行)
│    - 批量写入   │
└─────────────────┘
```

## 数据源

### 点踩数据

**表**: `account_center.common_feed_back_log`  
**筛选条件**:
- `scene = 'science_navigator'`
- `reaction_type = 2` (点踩)
- `status = 1` (有效)
- `create_time` 在指定日期范围

**关键字段**:
- `feed_back_remark` — 用户填写的点踩原因

**URL 拼接**: `https://www.bohrium.com/chat/share/{URL字段最后一段}?qid={session_id}`

### 评分数据

**表**: `account_center.user_behavior_record` JOIN `sigma-search.hot_session`  
**筛选条件**:
- `ubr.scene = 'scholar_QA'`
- `ubr.status = 1`
- `ubr.session_id LIKE 'adk_a_%'`
- `ubr.create_time` 在指定日期范围

**关键字段**:
- `target` — 评分分值（0-10 分）
- `remarks` — 用户填写的评分原因

**URL 拼接**: `https://www.bohrium.com/chat/share/{conversation_id}?qid={session_id}`

## 目标表格

**飞书多维表格**: https://dptechnology.feishu.cn/base/FQlvbn8yxaBOsPsVKsncPCA6nqc

### 字段映射

| 飞书字段 | 类型 | 填充规则 |
|---------|------|---------|
| url | 文本(URL) | 会话分享链接 |
| 问题描述 | 文本 | Claude 生成的问题描述（50-100字） |
| 问题层面 | 多选 | Claude 判断：产品/研发/设计 |
| 处理进度 | 单选 | 留空（由处理人手动更新） |
| 优先级 | 单选 | Claude 综合判断：P0/P1/P2 |
| 创建时间 | 日期 | 反馈创建时间 |
| 备注 | 文本 | 原始数据 JSON |
| 处理人 | 多人 | 用户手动 @ |

## Claude 归因规则

Claude 访问会话页面后，结合**会话内容**和**用户反馈原因**，完成两项判断：

### 问题层面（多选）

| 问题层面 | 判断依据 | 示例 |
|---------|---------|------|
| 产品层面 | **仅**用户的新功能需求、产品迭代建议 | "希望能导出 PDF"、"希望加一个论文对比功能"、"能不能支持多语言切换" |
| 研发层面 | AI 回答质量问题（截断、幻觉、编造事实、文献不全/陈旧、语言不匹配、意图理解偏差）、功能异常、报错、性能问题。**绝大多数反馈都属于此类** | "回答被截断"、"编造事实"、"搜索结果不相关"、"点击无响应"、"加载很慢" |
| 设计层面 | UI 显示问题、样式错误、视觉不一致 | "按钮位置不对"、"颜色看不清"、"排版错乱" |

### 优先级（单选）

Claude 综合以下信息判断优先级：
- 用户反馈原因（点踩的 `feed_back_remark` / 评分的 `remarks`）
- 评分分值（评分数据的 `target`，0-10 分）
- 会话内容（访问 URL 后阅读的实际对话）

| 优先级 | 判断标准 |
|--------|---------|
| P0（紧急） | 核心功能完全不可用、严重数据错误、极低评分（≤2分）且原因指向严重问题 |
| P1（重要） | 功能异常但有 workaround、回答质量明显偏差、点踩且原因指向明确 bug |
| P2（一般） | 体验优化类、回答基本可用但不够完善、UI 细节、中等评分且无严重问题 |

## 自动化运行

### 使用 cron（推荐）

```bash
# 每天早上 9 点运行，查询前一天的数据
0 9 * * * cd /path/to/xuling/sn-feedback-tracker && ./scripts/track_feedback.sh --date yesterday
```

### 使用 Claude Code /loop

在 Claude 对话中：

```
/loop 1d 查昨天的小导师反馈并归因写入飞书
```

## 权限要求

### DMS 权限

需要对以下表有查询权限：
- `account_center.common_feed_back_log`
- `account_center.user_behavior_record`
- `sigma-search.hot_session`

### 飞书权限

需要对目标多维表格有编辑权限：
- 创建记录
- 创建字段（如果字段不存在）

## 常见问题

### Q: 会话链接访问不了怎么办？

确保会话是公开分享的，或者 Claude 有权限访问。如果是内部会话，可能需要登录态。

### Q: Claude 归因不准确怎么办？

可以在飞书表格中手动修改"问题层面"和"问题描述"字段。后续可以收集这些修正数据来优化归因规则。

### Q: 数据量太大怎么办？

单日反馈超过 50 条时，建议：
1. 分批处理（先处理点踩，再处理评分）
2. 使用 `--type` 参数分别运行
3. 考虑只处理低评分（≤2分）的数据

### Q: 如何避免重复写入？

脚本会检查 URL 是否已存在于表格中（通过 `lark-cli base +record-list` 查询），已存在的会话会跳过。

## 文件结构

```
sn-feedback-tracker/
├── SKILL.md                      # Skill 定义
├── README.md                     # 本文件
└── scripts/
    ├── track_feedback.sh         # 主脚本：查询 DMS + 准备数据
    └── write_to_bitable.py       # Python 脚本：写入飞书
```

## 开发与调试

### 测试 DMS 查询

```bash
# 直接使用 dms_query.sh 测试
../link_dms_skill_for_claude_code/scripts/dms_query.sh \
  --instance "quickbi用" \
  --database "account_center" \
  --sql "SELECT * FROM common_feed_back_log WHERE scene='science_navigator' AND reaction_type=2 LIMIT 5"
```

### 测试飞书写入

```bash
# 使用 dry-run 模式
./scripts/track_feedback.sh --date yesterday --dry-run
```

### 手动归因测试

访问会话链接，手动判断问题层面，验证归因逻辑是否合理。

## 后续优化

- [ ] 支持批量归因（一次性处理多个会话）
- [ ] 归因结果缓存（避免重复访问同一会话）
- [ ] 自动检测重复问题（相似度匹配）
- [ ] 生成每日反馈报告（汇总统计）
- [ ] 支持自定义归因规则（配置文件）

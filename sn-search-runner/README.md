# SN Search Runner Skill

这个 skill 帮助你运行 Science Navigator (SN) AI 搜索，自动进行 AI 评分，并将结果写入飞书多维表格。

## 功能特性

- 从 CSV / JSON / XLSX 文件批量导入查询，**多线程并发**执行
- 自动对 query **去重**，避免重复搜索
- 每次搜索自动进行 **AI 评分**（15 个维度，含满分/扣分理由）
- 通过 **Opik** 获取 LLM trace 信息，提升评分准确性
- 结果自动写入**飞书多维表格**（通过 lark-cli）
- 同一批次共用 `task_id`（格式 `task_时间戳`），方便按批次筛选
- papers 字段输出结构化 list of dict（支持论文、百科、网页、新闻四种类型）

## 项目结构

```
sn-search-runner/
├── scripts/
│   ├── run_search.py        # 主入口：批量搜索 + AI 评分 + 写飞书
│   ├── sn_search.py         # SN 搜索 API 客户端
│   ├── agent_workflow.py    # Dify AI 评分工作流
│   ├── opik_client.py       # Opik trace 查询客户端
│   ├── const.py             # Opik 环境配置
│   └── lark_bitable.py      # 飞书多维表格操作模块
├── examples/
│   ├── queries.csv          # 查询文件示例（CSV 格式）
│   ├── queries.json         # 查询文件示例（JSON 格式）
│   └── query.xlsx           # 查询文件示例（XLSX 格式）
└── README.md
```

## 使用方式

### 1. 获取 API Token

1. 打开 https://www.bohrium.com 并登录
2. 打开浏览器开发者工具（F12）
3. 切换到 Network 标签
4. 执行任意操作触发 API 请求
5. 在请求头中找到 `Authorization` 字段
6. 复制 `Bearer ` 后面的 token 值（不要包含 "Bearer " 本身）

### 2. 准备查询文件

支持三种格式，每条 query 可独立指定 `discipline` 和 `journal_type`（不填则默认 `All` / `both`）：

**queries.csv:**
```csv
query,discipline,journal_type
胆道闭锁的最新研究,All,both
图神经网络在药物发现中的应用,NS,foreign
CRISPR基因编辑技术进展,LS,both
```

**queries.json:**
```json
[
  {
    "query": "胆道闭锁的最新研究",
    "discipline": "All",
    "journal_type": "both"
  },
  {
    "query": "图神经网络在药物发现中的应用",
    "discipline": "NS",
    "journal_type": "foreign"
  }
]
```

**query.xlsx:**

Excel 文件需包含 `query` 列，可选 `discipline` 和 `journal_type` 列。

### 3. 配置 API 密钥

需要配置三个密钥：

#### 3.1 配置 Bohrium API Token

编辑 `scripts/run_search.py` 底部的配置区：

```python
# ============ 配置区 ============
TOKEN = "your-token-here"                                              # API Token（按步骤 1 获取）
QUERY_FILE = str(_SCRIPT_DIR.parent / "examples" / "queries.csv")      # 查询文件路径（.csv / .json / .xlsx）
WORKERS = 3                                                            # 并发线程数
# ======================================
```

#### 3.2 配置 Dify API Key

编辑 `scripts/agent_workflow.py` 顶部：

```python
API_KEY = "your-dify-api-key-here"  # Dify 工作流 API Key
```

获取方式：登录 Dify 平台，进入对应的工作流，在「API 访问」中复制 API Key。

#### 3.3 配置飞书多维表格

编辑 `scripts/lark_bitable.py` 顶部：

```python
LARK_APP_TOKEN = ""   # 多维表格 app_token（参考下方说明获取）
LARK_TABLE_ID = ""    # 数据表 table_id，留空则自动创建
```

获取方式见下方「如何获取 LARK_APP_TOKEN」和「如何获取 LARK_TABLE_ID」。

### 4. 运行搜索

#### 4.1 单条查询

传入 query 参数即可：

```bash
cd scripts
python3 run_search.py "深度势能是什么"
python3 run_search.py "CRISPR基因编辑技术进展" LS foreign
```

#### 4.2 批量查询

不传参数，直接运行，会从 `QUERY_FILE` 配置的文件批量执行：

```bash
cd scripts
python3 run_search.py
```

批量模式会：
1. 从文件读取 query 并自动去重
2. 生成批次 `task_id`（如 `task_1744896000`）
3. 多线程并发执行搜索 → AI 评分 → 写入飞书
4. 输出执行进度和成功/失败统计

## 执行流程

```
读取查询文件 → 去重 → 并发执行:
  ┌─ SN AI 搜索（bohrium API）
  ├─ Opik trace 查询（获取 LLM span）
  ├─ Dify AI 评分（15 个维度 + 满分/扣分理由）
  └─ 写入飞书多维表格（lark-cli）
```

## 飞书多维表格字段

搜索结果会自动写入飞书多维表格，字段包括：

| 分类 | 字段 |
|------|------|
| 基础信息 | query, session_id, share_url, keywords, sub_query, summary, papers, papers_count, evidence_search, summary_first_token |
| AI 分析 | ai_analysis |
| 元数据 | model, scene, env, task |
| 自动字段 | 创建时间（飞书自动填充） |
| 评分（15 个维度） | 忠实度评分, 回答相关性评分, 上下文相关性评分, 上下文精确率评分, 首次响应时间评分, 文献时效性评分, Top6文献时效性评分, 文献质量评分, Top6文献质量评分, 回答完整性, 思考过程 / Query 改写准确性, 证据检索来源相关性, 输出格式自适应能力, 限制条件识别能力, 回答逻辑性 |
| 评分理由 | 每个维度拆分为 `xxx满分理由` 和 `xxx扣分理由`，紧跟在对应评分字段后 |

#### 如何获取 LARK_APP_TOKEN

`LARK_APP_TOKEN` 是飞书多维表格的唯一标识，获取方式：

1. 在飞书中打开（或新建）一个多维表格
2. 查看浏览器地址栏，URL 格式为：
   ```
   https://xxx.feishu.cn/base/{app_token}?table={table_id}&view={view_id}
   ```
3. 复制 URL 中 `/base/` 后面、`?` 前面的部分，即为 `LARK_APP_TOKEN`

例如 URL 为 `https://xxx.feishu.cn/base/PGh0wcTuCie31Qkk9fhc1cVAnVh?table=tblXXX`，则 `LARK_APP_TOKEN = "PGh0wcTuCie31Qkk9fhc1cVAnVh"`。

#### 如何获取 LARK_TABLE_ID

`LARK_TABLE_ID` 是多维表格中某张数据表的 ID：

- **自动创建**：将 `LARK_TABLE_ID` 留空（`""`），程序首次运行时会自动创建名为「SN搜索评测结果」的数据表，并自动配置所有字段
- **使用已有表**：从浏览器地址栏 URL 的 `?table=` 参数中复制，例如 `tbl4QnrcJZEHXFRd`

> **注意**：复制时只取 `table=` 后面到 `&` 之前的部分，不要带上 `&view=...` 等其他参数。

## 参数说明

### discipline（学科范围，可选）

| 值 | 含义 |
|---|---|
| `"All"` | 全部（默认） |
| `"NS"` | 自然科学 |
| `"ET"` | 工程技术 |
| `"LS"` | 生命科学 |
| `"PSS"` | 哲学与社会科学 |

### journal_type（期刊范围，可选）

| 值 | 含义 |
|---|---|
| `"both"` | 全部期刊（默认） |
| `"foreign"` | 国际期刊 |
| `"chinese"` | 中国期刊 |
| `"chinese_tech"` | 科协期刊集群 |

**固定参数（在代码中配置）：**
- model: `"reason"`
- scene: `"adk_science_navigator"`
- env: `"uat"`

## 依赖要求

- Python 3
- requests
- openpyxl（读取 xlsx 文件）
- opik（Opik trace 查询）
- lark-cli（飞书 API 调用，需提前安装并认证）

## 注意事项

- Token 有有效期，过期后需要重新获取
- 批量搜索时，单条失败不影响其余查询，错误会记录日志并继续
- 同一文件中重复的 query 会自动去重，只执行一次
- 并发线程数通过 `WORKERS` 配置，建议 3~5
- 首次运行时会自动在飞书表中创建缺失字段

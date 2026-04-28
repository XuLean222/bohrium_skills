---
name: dms-sql-query-export
description: 通过阿里云 CLI 查询 DMS 数据库 SQL 并导出数据。适用于 dms.aliyun.com、数据管理 DMS、aliyun dms-enterprise、张家口地域、预置场景查询、导出工单等场景。
---

# DMS：通过阿里云 CLI 查询 SQL 与导出数据

## 概述

本 Skill 帮助用户通过阿里云 CLI 调用 DMS Enterprise OpenAPI，实现 SQL 查询和数据导出，无需打开 DMS 控制台。

## 固定配置

```bash
REGION=cn-zhangjiakou
ENDPOINT=dms-enterprise.cn-zhangjiakou.aliyuncs.com
```

所有 `aliyun dms-enterprise ...` 命令均需携带 `--region` 和 `--endpoint` 参数。

## 前置条件

1. **阿里云 CLI**：已安装并执行 `aliyun configure` 配置凭证
2. **RAM 权限**：由运维开通 DMS 相关 API 权限（如 `AliyunDMSFullAccess`）
3. **jq**：用于 JSON 处理（`brew install jq`）
4. **实例要求**：`ExecuteScript` 需安全托管实例；导出工单需安全协同模式

## 工作流

### A. 解析 DbId（执行 SQL 前必做）

```bash
# 1. 根据实例别名查找 InstanceId
aliyun dms-enterprise ListInstances --region "$REGION" --endpoint "$ENDPOINT" \
  --SearchKey "<实例别名>" --PageSize 100

# 2. 根据 InstanceId 查找 DatabaseId
aliyun dms-enterprise ListDatabases --region "$REGION" --endpoint "$ENDPOINT" \
  --InstanceId "<InstanceId>" --SearchKey "<库名>"
```

### B. 执行 SQL（即时查询）

```bash
aliyun dms-enterprise ExecuteScript \
  --region "$REGION" --endpoint "$ENDPOINT" \
  --DbId <DbId> \
  --Logic <true|false> \
  --Script '<SQL语句>'
```

### C. 导出工单（大结果集）

1. **创建工单**：`CreateDataExportOrder`
2. **人工审批**：将工单 ID 交给库负责人在 DMS 控制台审批
3. **执行导出**：审批通过后执行 `ExecuteDataExport`
4. **获取链接**：`GetDataExportDownloadURL`

## 预置场景

使用 `scripts/dms_query.sh` 快速执行预置查询：

```bash
# 列出所有场景
./scripts/dms_query.sh --list-scenarios

# 执行场景（即时查询）
./scripts/dms_query.sh --scenario <序号>

# 执行场景（创建导出工单）
./scripts/dms_query.sh --scenario <序号> --export
```

| 序号 | 场景 | 实例 | 库 |
|-----|------|------|-----|
| 1 | 查询200条sn用户提问 | quickbi用 | sigma-search |
| 2 | 用户对玻尔全站的反馈 | quickbi用 | account_center |
| 3 | 会话级别查询天级创建session数量 | quickbi用 | sigma-search |
| 4 | question级别查询天级创建question数量 | quickbi用 | sigma-search |
| 5 | 天级平台统计数 | quickbi用 | sigma-search |
| 6 | 会话级别查询月级创建session数量 | quickbi用 | sigma-search |
| 7 | question级别查询月级创建question数量 | quickbi用 | sigma-search |
| 8 | 不同用户类型使用不同模式的session数 | quickbi用 | sigma-search |
| 9 | AI小导师的用户点赞查询 | quickbi用 | account_center |
| 10 | AI小导师的用户点踩查询 | quickbi用 | account_center |
| 11 | AI小导师的用户点赞点踩联查 | quickbi用 | account_center |
| 12 | AI小导师的用户评分查询 | quickbi用 | account_center |
| 13 | AI小导师的问题数及原生query | bohrium-opik-test | public |
| 14 | AI小导师的问题数及分享情况 | quickbi用 | sigma-search |

## Examples

- 用户说「帮我查场景 11」→ 执行 `./scripts/dms_query.sh --scenario 11`
- 用户说「导出 AI 小导师点赞数据」→ 执行 `./scripts/dms_query.sh --scenario 9 --export`
- 用户说「在 account_center 库执行这条 SQL」→ 先解析 DbId，再 `ExecuteScript`

## Guidelines

1. **先确认环境**：检查 `aliyun` CLI 和凭证是否配置正确
2. **先解析 ID**：执行 SQL 前必须先获取 `DbId` 和确认 `Logic`（逻辑库/物理库）
3. **导出需审批**：`CreateDataExportOrder` 后必须等人工审批通过，才能 `ExecuteDataExport`
4. **不要代填密钥**：AccessKey 由用户自行配置，不提交到 Git
5. **预置场景优先**：用户提到场景编号或标题时，优先使用 `dms_query.sh --scenario`

## 常见问题

| 现象 | 解决 |
|------|------|
| `InvalidAccessKeyId.NotFound` | 检查是否为中国站 RAM 的 AccessKey |
| `unknown endpoint` | 确认命令包含 `--endpoint "$ENDPOINT"` |
| `HasResult: false` | 先执行 `ExecuteDataExport`，等任务完成 |
| `bad flag format --output` | 不要用 `--output json`，CLI 3.x 默认即 JSON |

## 参考链接

- [DMS API 概览](https://help.aliyun.com/zh/dms/developer-reference/api-dms-enterprise-2018-11-01-overview)
- [ExecuteScript](https://help.aliyun.com/zh/dms/developer-reference/api-dms-enterprise-2018-11-01-executescript)
- [CreateDataExportOrder](https://help.aliyun.com/zh/dms/developer-reference/api-dms-enterprise-2018-11-01-createdataexportorder)
- [阿里云 CLI 配置凭证](https://help.aliyun.com/zh/cli/configure-credentials)

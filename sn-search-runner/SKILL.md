---
name: sn-search-runner
description: Run AI search queries using the SN (Science Navigator) search API and get structured, readable results. Use this skill whenever the user wants to run SN searches, test search results, evaluate search quality, or get AI-generated summaries with paper citations. Trigger when user mentions "run SN search", "test search", "query SN", "search for [topic]", or provides search queries to execute. Also trigger when user wants to batch test multiple queries or evaluate search performance.
---

# SN Search Runner

This skill helps you run AI search queries against the Science Navigator (SN) API and format the results into readable, structured JSON files.

## When to Use This Skill

Use this skill when the user wants to:
- Run one or more search queries through the SN AI search system
- Test or evaluate search results quality
- Get AI-generated research summaries with paper citations
- Batch process multiple search queries
- Compare search results across different parameters

## Prerequisites

Before running searches, ensure:
1. Python 3 is installed
2. The `requests` library is available
3. A virtual environment is set up (if not in one already)
4. The user has provided a valid API token

## Getting the API Token

The user needs to provide an API token. Here's how to obtain it:

1. Open the production Bohrium website (https://www.bohrium.com)
2. Log in to your account
3. Open browser DevTools (F12 or right-click → Inspect)
4. Go to the Network tab
5. Perform any action that triggers an API call
6. Find any API request in the network log
7. Look at the request headers
8. Find the `Authorization` header
9. Copy the value after `Bearer ` (do NOT include the word "Bearer" itself)

**Important**: The token is just the long string after "Bearer ", not including "Bearer " itself.

## Search Parameters

### discipline（学科范围）

| 值 | 含义 |
|---|---|
| `"All"` | 全部（默认） |
| `"NS"` | 自然科学 |
| `"ET"` | 工程技术 |
| `"LS"` | 生命科学 |
| `"PSS"` | 哲学与社会科学 |

### journal_type（期刊范围）

| 值 | 含义 |
|---|---|
| `"both"` | 全部期刊（默认） |
| `"foreign"` | 国际期刊 |
| `"chinese"` | 中国期刊 |
| `"chinese_tech"` | 科协期刊集群 |

### Fixed Parameters (cannot be changed)

- `model`: always `"pro"`
- `scene`: always `"adk_science_navigator"`
- `env`: always `"prod"`

## How to Run Searches

### Single Query

When the user provides a single query:

```
User: "Run a search for: 胆道闭锁的最新研究"
```

Ask for their token if they haven't provided it, then run the search.

### Multiple Queries (Inline)

When the user provides multiple queries in the conversation:

```
User: "Run searches for:
1. 胆道闭锁的最新研究
2. 图神经网络在药物发现中的应用
3. CRISPR基因编辑技术进展"
```

Process each query sequentially.

### Batch from File

When the user provides a file with queries:

**CSV format** (`queries.csv`):
```csv
query,discipline,journal_type
胆道闭锁的最新研究,All,both
图神经网络在药物发现中的应用,NS,foreign
CRISPR基因编辑技术进展,LS,both
```

**JSON format** (`queries.json`):
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

## Implementation Steps

### 1. Check Environment and Dependencies

First, verify the environment is ready:

```bash
# Check if in a virtual environment
python3 -c "import sys; print('venv' if sys.prefix != sys.base_prefix else 'no venv')"

# Check if requests is installed
python3 -c "import requests" 2>/dev/null && echo "requests installed" || echo "requests not installed"
```

If not in a venv or requests is missing:
- Create a venv in the current directory: `python3 -m venv .venv`
- Activate it: `source .venv/bin/activate`
- Install requests: `pip install requests`

### 2. Set Up the Search Scripts

**`sn_search.py`** — The main search client. It should already exist in the user's workspace at `/Users/dp/Documents/新版 sn 需求/效果评估/sn_search.py`.

Key points about `sn_search.py`:
- The `SNSearch` class handles API calls to `https://www.bohrium.com`
- `format_mix_papers()` and `format_papers()` return **structured list of dict** (not strings)
- Each paper dict has a `type` field: `"paper"`, `"science-pedia"`, `"web"`, or `"news"`

### 3. Run the Searches

**For single query** (use the script directly in Python or via CLI):

```python
from sn_search import SNSearch

token = "<your-token>"
query = "胆道闭锁治疗最新方案"

sn_search = SNSearch("prod", "adk_science_navigator", token, "", "", "")
result = sn_search.ai_search_result(query, "pro", "All", "both")

# result["papers"] is already a list of structured dicts
for paper in result["papers"]:
    print(f"[{paper['type']}] {paper['Title']}")
```

**For batch queries from file:**

```bash
cd "/Users/dp/Documents/新版 sn 需求/效果评估"
source .venv/bin/activate
python batch_search.py "<token>" queries.json ./results
```

### 4. Handle Different Input Formats

When the user provides queries:

**Inline multiple queries**: Parse them from the conversation, create a temporary JSON file, then run batch processing.

**File provided**: Use the file directly with batch processing.

**Single query**: Run directly via Python.

## Output Format

Each search produces a JSON file named `{query}_{timestamp}.json` with this structure:

```json
{
  "session_id": "...",
  "share_url": "https://www.bohrium.com/chat/share/...",
  "keywords": [...],
  "sub_query": [...],
  "summary": "...",
  "papers": [
    {
      "type": "paper",
      "Title": "...",
      "Author": ["Author1", "Author2"],
      "Journal": "...",
      "Abstract": "...",
      "doi": "...",
      "PublicationDate": "2025-01-15",
      "citation_id": "..."
    },
    {
      "type": "science-pedia",
      "Title": "...",
      "snippet": "...",
      "url": "https://sciencepedia.bohrium.com/article/...",
      "key_points": "...",
      "citation_id": "..."
    },
    {
      "type": "web",
      "Title": "...",
      "site": "...",
      "snippet": "...",
      "url": "...",
      "citation_id": "..."
    },
    {
      "type": "news",
      "Title": "...",
      "site": "...",
      "snippet": "...",
      "url": "...",
      "data_source": "...",
      "date": "...",
      "citation_id": "..."
    }
  ],
  "evidence_search": [...],
  "summary_first_token": 10000
}
```

The `papers` field is a structured list of dicts. Each item has a `type` field to distinguish content types, and all fields are cleanly separated — no string parsing needed.

## Error Handling

If a search fails:
- Check the token is valid (not expired)
- Verify network connectivity
- Check the API response for error messages
- Log the error and continue with remaining queries (in batch mode)

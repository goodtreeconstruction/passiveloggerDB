---
name: passiveloggerDB
description: >
  Query the ChromaDB semantic memory database for conversation history, project context,
  crash recovery, and cross-session recall. Use when user says "you crashed", "what were
  we working on", "continue where we left off", "what did Cypress do", "find that config",
  "what was the decision about X", or any request needing context from past Claude Desktop
  sessions. Also use for "check memory", "search logs", "what happened today/yesterday".
---

# PassiveLoggerDB - Semantic Memory Query Skill

## Overview

ChromaDB-based semantic search over all passive logger captures from Claude Desktop.
Contains conversation history from all sessions (human + claude messages), embedded
with MiniLM and queryable by meaning, date, role, and source machine.

- **Query API**: `http://localhost:8000/api/rag/query` (POST)
- **Stats**: `http://localhost:8000/api/rag/stats` (GET)
- **Health**: `http://localhost:8000/health` (GET)
- **DB Path**: `C:\Users\Matthew\Documents\claude\forest-memory\chromadb`
- **GitHub**: `https://github.com/goodtreeconstruction/passiveloggerDB`

## When to Use This Skill

- User says "you crashed", "timed out", "where did we leave off"
- User asks "what were we working on?" or "continue X project"
- User references past decisions: "what did we decide about...", "what port was..."
- User asks about other agents: "what has Cypress been doing?"
- User needs technical recall: configs, paths, architecture from past sessions
- User says "check memory", "search logs", "find in history"
- User asks "have we seen this error before?"
- You (Claude) need context before starting work on a known project
- Starting a new session and user references ongoing work

## Query API

### POST /api/rag/query

```json
{
  "query": "semantic search text here",
  "top_k": 5,
  "days": 7,
  "role": "human",
  "source": "redwood"
}
```

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| query | string | required | Natural language search |
| top_k | int | 5 | Max results (up to 20) |
| days | int | null | Filter to last N days |
| role | string | null | "human" or "claude" |
| source | string | null | Machine: "redwood", "elm", "cypress" |

**Score interpretation:** 0.70+ strong, 0.50-0.70 good, 0.30-0.50 weak, <0.30 noise

## How to Query

### Primary Method (Desktop Commander)

```
Desktop Commander:start_process
command: python -c "import requests,json; r=requests.post('http://localhost:8000/api/rag/query', json={'query':'YOUR SEARCH','top_k':5}); d=r.json(); [print(f'[{x[\"score\"]:.2f}] {x[\"date\"]} ({x[\"role\"]}) {x[\"content\"][:200]}') for x in d.get('results',[])]"
timeout_ms: 15000
```

### Fallback (Direct ChromaDB, if server is down)

```python
import chromadb
client = chromadb.PersistentClient(path=r"C:\Users\Matthew\Documents\claude\forest-memory\chromadb")
col = client.get_collection("forest_memory")
results = col.query(query_texts=["YOUR SEARCH"], n_results=5)
for i, doc in enumerate(results["documents"][0]):
    meta = results["metadatas"][0][i]
    dist = results["distances"][0][i]
    print(f"[{1-dist:.2f}] {meta['date']} ({meta['role']}) {doc[:200]}")
```

## Use Case Workflows

### 1. Crash Recovery
User says "you crashed" or "where did we leave off":
1. Query recent claude activity: `{"query": "working on building implementing", "top_k": 10, "days": 1}`
2. Query recent human requests: `{"query": "please help build fix create", "top_k": 5, "days": 1, "role": "human"}`
3. Summarize findings and ask user to confirm

### 2. Project Context Loading
User says "let's work on GoodTree" or "continue Jarvis":
1. Query project: `{"query": "GoodTree estimator dashboard bot", "top_k": 10, "days": 7}`
2. Summarize recent state before diving in

### 3. Agent Coordination
User asks "what has Cypress been doing?":
1. Query: `{"query": "Cypress working setup building", "top_k": 10, "days": 3}`

### 4. Technical Detail Recall
User asks "what port was X on?":
1. Query with specific terms: `{"query": "port 8000 forest chat webhook", "top_k": 5}`

### 5. Debugging History
User says "have we seen this error before?":
1. Query the error text: `{"query": "UnicodeDecodeError charmap codec", "top_k": 5}`

### 6. Daily Summary
User asks "what happened today?":
1. Claude activity: `{"query": "implemented configured built fixed", "top_k": 20, "days": 1}`
2. Human requests: `{"query": "help build create fix", "top_k": 10, "days": 1, "role": "human"}`

## Service Management

### Check if running
```
python -c "import requests; r=requests.get('http://localhost:8000/health'); print(r.json())"
```

### Start Query Server
```
Start-Process python -ArgumentList "-u","C:\Users\Matthew\Documents\claude\forest-memory\rag\query_server.py" -WindowStyle Hidden
```

### Start Logger
```
python -u C:\Users\Matthew\Documents\claude\passive-logger\claude_uia_logger_v2.py --force
```

### Backfill historical logs
```
python C:\Users\Matthew\Documents\claude\forest-memory\rag\backfill_chroma.py --all
```

## Key Files

| File | Location |
|------|----------|
| Logger v20 | `C:\Users\Matthew\Documents\claude\passive-logger\claude_uia_logger_v2.py` |
| Query Server | `C:\Users\Matthew\Documents\claude\forest-memory\rag\query_server.py` |
| Backfill | `C:\Users\Matthew\Documents\claude\forest-memory\rag\backfill_chroma.py` |
| ChromaDB | `C:\Users\Matthew\Documents\claude\forest-memory\chromadb\` |
| Recovery file | `C:\Users\Matthew\Documents\claude\passive-logger\logs\current_stream.recovery` |

## Notes

- DB contains Claude Desktop captures only (not claude.ai web sessions)
- Source is "redwood" only currently (expand when other machines get loggers)
- Logger embeds on final capture only (no streaming duplicates)
- Uses MiniLM-L6-v2 embeddings (384-dim, ~80MB model, cosine similarity)
- If 0 results unexpectedly, verify server is running on port 8000

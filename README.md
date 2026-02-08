# PassiveLoggerDB

ChromaDB-powered semantic memory system for AI conversation logs. Works with the [passive-logger](https://github.com/goodtreeconstruction/passive-logger) to provide searchable, embedded memory across all conversations.

## Architecture

```
Passive Logger (UIA) -> Final captures only -> ChromaDB (MiniLM embeddings)
                                                    |
                                            Query API (port 8000)
                                                    |
                                        AI agents query semantically
```

## Key Features

- **Event-driven embedding**: Each final capture is embedded into ChromaDB in real-time (~50ms)
- **No LLM required**: Uses `all-MiniLM-L6-v2` embeddings (79MB model, no Ollama/GPU needed)
- **~200MB RAM** vs 5GB with Ollama/Mistral approach
- **Sub-second queries** vs 52-64 seconds with local LLM
- **Metadata filtering**: Query by date, time, role (human/claude), source machine
- **Deduplication**: Only final messages embedded, streaming snapshots go to `.recovery` file

## Files

| File | Purpose |
|------|---------|
| `query_server.py` | REST API for semantic search (port 8000) |
| `backfill_chroma.py` | Import existing .jsonl logs into ChromaDB |

## Query API

### POST /api/rag/query
```json
{
  "query": "Tailscale access setup",
  "top_k": 5,
  "days": 7,
  "role": "claude",
  "source": "redwood"
}
```

### GET /api/rag/stats
Returns collection statistics.

### GET /health
Health check with entry count.

## Setup

```bash
pip install chromadb
python backfill_chroma.py --all    # Import existing logs
python query_server.py              # Start query API on port 8000
```

## Performance

| Metric | Old (Mistral 7B) | New (ChromaDB) |
|--------|-------------------|----------------|
| Query time | 52-64 seconds | <2.5 seconds |
| RAM usage | ~5 GB | ~200 MB |
| Best relevance score | 0.47 | 0.75 |
| Embedding model | Mistral 7B (4096-dim) | MiniLM-L6 (384-dim) |
| Answer generation | Local LLM (slow, often wrong) | Raw chunks (AI interprets) |

## Integration with Passive Logger

The logger (v20+) has ChromaDB built in. On every final capture it:
1. Writes to `.md` and `.jsonl` (clean, no streaming dupes)
2. Embeds to ChromaDB with metadata (date, time, role, source)
3. Streaming crash-recovery goes to `.recovery` file only

## License
MIT

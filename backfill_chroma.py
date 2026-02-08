"""
Backfill existing passive logger .jsonl files into ChromaDB.
Run once to seed the database with historical logs.
Uses ChromaDB's built-in MiniLM embeddings - no Ollama needed.

Usage: python backfill_chroma.py           # Today's logs
       python backfill_chroma.py --all     # All available logs
       python backfill_chroma.py --date 2026-02-07
"""

import json
import hashlib
import sys
from pathlib import Path
from datetime import datetime, timedelta

import chromadb

LOG_DIR = Path(r"C:\Users\Matthew\Documents\claude\passive-logger\logs")
CHROMA_DB_PATH = r"C:\Users\Matthew\Documents\claude\forest-memory\chromadb"
COLLECTION_NAME = "forest_memory"

def backfill(dates=None, all_dates=False):
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    col = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )
    print(f"[*] ChromaDB: {col.count()} existing entries")
    
    # Find log files
    if all_dates:
        jsonl_files = sorted(LOG_DIR.rglob("*.jsonl"))
    elif dates:
        jsonl_files = []
        for d in dates:
            month = d[:7]
            p = LOG_DIR / month / f"{d}.jsonl"
            if p.exists():
                jsonl_files.append(p)
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        month = today[:7]
        p = LOG_DIR / month / f"{today}.jsonl"
        jsonl_files = [p] if p.exists() else []
    
    if not jsonl_files:
        print("[!] No .jsonl files found")
        return
    
    total = 0
    for jf in jsonl_files:
        date_str = jf.stem  # e.g. "2026-02-08"
        print(f"\n[*] Processing {jf.name}...")
        
        ids, docs, metas = [], [], []
        with open(jf, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                # Skip streaming snapshots (old format had these)
                if entry.get("streaming", False):
                    continue
                
                text = entry.get("text", "").strip()
                if not text or len(text) < 10:
                    continue
                
                ts = entry.get("timestamp", "")
                role = entry.get("role", "unknown")
                doc_id = hashlib.md5(f"{ts}:{text[:200]}".encode()).hexdigest()
                
                time_str = ""
                if "T" in ts:
                    time_str = ts.split("T")[1][:8]
                
                ids.append(doc_id)
                docs.append(text[:4000])
                metas.append({
                    "role": role,
                    "date": date_str,
                    "time": time_str,
                    "timestamp": ts,
                    "source": "redwood",
                    "char_count": len(text),
                })
        
        # Deduplicate by ID (keep last/longest version)
        seen = {}
        for i, doc_id in enumerate(ids):
            if doc_id not in seen or len(docs[i]) > len(docs[seen[doc_id]]):
                seen[doc_id] = i
        unique_idx = sorted(seen.values())
        ids = [ids[i] for i in unique_idx]
        docs = [docs[i] for i in unique_idx]
        metas = [metas[i] for i in unique_idx]
        
        if not ids:
            print(f"  [SKIP] No valid entries (all streaming or empty)")
            continue
        
        # Batch upsert (ChromaDB handles embedding automatically)
        batch_size = 50
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i+batch_size]
            batch_docs = docs[i:i+batch_size]
            batch_metas = metas[i:i+batch_size]
            col.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
            print(f"  Embedded batch {i//batch_size + 1} ({len(batch_ids)} entries)")
        
        total += len(ids)
        print(f"  [OK] {len(ids)} entries embedded from {jf.name}")
    
    print(f"\n[DONE] {total} entries backfilled. Collection now has {col.count()} total.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--date", type=str, nargs="*")
    args = parser.parse_args()
    backfill(dates=args.date, all_dates=args.all)

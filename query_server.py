"""
Forest Memory RAG - Query Server (ChromaDB)
=============================================
REST API for semantic search over conversation logs.
Uses ChromaDB with built-in MiniLM embeddings. No Ollama needed.

Endpoints:
  POST /api/rag/query   - Semantic search with optional filters
    Body: {"query": "...", "top_k": 5, "days": 7, "role": "human|claude"}
    Returns: {"results": [...], "count": N}

  GET  /api/rag/stats    - Collection statistics
  GET  /health           - Health check

Run: python query_server.py
Port: 8000
"""

import json
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

import chromadb

CHROMA_DB_PATH = r"C:\Users\Matthew\Documents\claude\forest-memory\chromadb"
CHROMA_COLLECTION = "forest_memory"
PORT = 8000

# Initialize ChromaDB client (collection refreshed per-request for live data)
client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

def get_collection():
    """Get fresh collection reference to see live updates from logger."""
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )

class QueryHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        col = get_collection()
        if self.path == "/health":
            self._send_json({"status": "ok", "entries": col.count()})
        elif self.path == "/api/rag/stats":
            self._send_json({
                "collection": CHROMA_COLLECTION,
                "total_entries": col.count(),
                "db_path": CHROMA_DB_PATH,
            })
        elif self.path == "/":
            self._send_json({
                "service": "Forest Memory RAG",
                "version": "2.0-chromadb",
                "entries": col.count(),
                "endpoints": ["/api/rag/query (POST)", "/api/rag/stats", "/health"]
            })
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/api/rag/query":
            self._send_json({"error": "not found"}, 404)
            return
        
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
        except Exception:
            self._send_json({"error": "invalid json"}, 400)
            return
        
        query = body.get("query", "").strip()
        if not query:
            self._send_json({"error": "query required"}, 400)
            return
        
        top_k = min(body.get("top_k", 5), 20)
        days = body.get("days", None)
        role_filter = body.get("role", None)
        source_filter = body.get("source", None)
        
        # Build metadata filter
        where_filter = {}
        conditions = []
        
        if days:
            # ChromaDB can't do $gte on strings, so generate list of valid dates
            date_list = [(datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d") for d in range(days)]
            conditions.append({"date": {"$in": date_list}})
        if role_filter:
            conditions.append({"role": role_filter})
        if source_filter:
            conditions.append({"source": source_filter})
        
        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$and": conditions}
        
        # Query ChromaDB
        try:
            kwargs = {
                "query_texts": [query],
                "n_results": top_k,
            }
            if where_filter:
                kwargs["where"] = where_filter
            
            col = get_collection()
            results = col.query(**kwargs)
            
            formatted = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i] if results["metadatas"] else {}
                    dist = results["distances"][0][i] if results["distances"] else None
                    formatted.append({
                        "content": doc,
                        "score": round(1 - dist, 4) if dist is not None else None,
                        "date": meta.get("date", ""),
                        "time": meta.get("time", ""),
                        "role": meta.get("role", ""),
                        "source": meta.get("source", ""),
                        "char_count": meta.get("char_count", 0),
                    })
            
            self._send_json({"results": formatted, "count": len(formatted), "query": query})
        
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def log_message(self, format, *args):
        # Quiet logging
        pass

if __name__ == "__main__":
    print(f"[*] Forest Memory RAG Query Server v2.0 (ChromaDB)")
    print(f"[*] DB: {CHROMA_DB_PATH}")
    col = get_collection()
    print(f"[*] Collection: {CHROMA_COLLECTION} ({col.count()} entries)")
    print(f"[*] Listening on http://0.0.0.0:{PORT}")
    server = HTTPServer(("0.0.0.0", PORT), QueryHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Stopped.")

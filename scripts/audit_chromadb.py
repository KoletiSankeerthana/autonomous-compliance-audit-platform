import sys
import os

# Add backend directory to sys.path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.rag_service import _collection

def run_audit():
    try:
        results = _collection.get(include=["metadatas"])
        metadatas = results.get("metadatas") or []
        
        print(f"Total chunks in ChromaDB: {len(metadatas)}")
        
        source_counts = {}
        for m in metadatas:
            if not m: continue
            src = m.get("source", "unknown")
            
            doc_id = m.get("notion_page_id") or m.get("drive_file_id") or m.get("filename") or "unknown_doc"
            
            if src not in source_counts:
                source_counts[src] = {"chunks": 0, "docs": set()}
                
            source_counts[src]["chunks"] += 1
            source_counts[src]["docs"].add(doc_id)
            
        for src, stats in source_counts.items():
            print(f"Source: {src}")
            print(f"  Chunks: {stats['chunks']}")
            print(f"  Unique Docs: {len(stats['docs'])}")
            
    except Exception as e:
        print(f"Audit failed: {e}")

if __name__ == "__main__":
    run_audit()

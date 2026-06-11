import sys
import os
from collections import Counter

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.services.rag_service import _collection

def run_google_drive_audit():
    results = _collection.get(where={"source": "google_drive"}, include=["metadatas", "documents"])
    metadatas = results.get("metadatas") or []
    documents = results.get("documents") or []
    ids = results.get("ids", [])

    file_stats = {}
    total_chunks = len(metadatas)
    unique_drive_ids = set()
    total_duplicates = 0
    re_ingested_files = set()
    seen_file_chunks = {}

    for meta, doc, chunk_id in zip(metadatas, documents, ids):
        if not meta: continue
        fname = meta.get("filename") or meta.get("drive_file_name") or "unknown"
        drive_id = meta.get("drive_file_id", "missing_id")
        modified_time = meta.get("last_modified", "N/A")
        
        if fname not in file_stats:
            file_stats[fname] = {
                "drive_file_id": drive_id,
                "chunk_count": 0,
                "first_chunk_id": chunk_id,
                "last_chunk_id": chunk_id,
                "last_modified": modified_time,
                "duplicates": 0
            }
        
        file_stats[fname]["chunk_count"] += 1
        file_stats[fname]["last_chunk_id"] = chunk_id
        
        if drive_id != "missing_id":
            unique_drive_ids.add(drive_id)
            
        chunk_sig = (fname, hash(doc))
        if chunk_sig in seen_file_chunks:
            file_stats[fname]["duplicates"] += 1
            total_duplicates += 1
            re_ingested_files.add(fname)
        else:
            seen_file_chunks[chunk_sig] = True

    print("--- AUDIT REPORT CONTENT ---")
    print(f"Unique Google Drive file count: {len(file_stats)}")
    print(f"Unique drive_file_id count: {len(unique_drive_ids)}")
    print(f"Total Google Drive chunks: {total_chunks}")
    print(f"Duplicate chunk count: {total_duplicates}")
    print(f"Files re-ingested multiple times: {', '.join(re_ingested_files) if re_ingested_files else 'None'}")
    
    print("\nMetadata sample:")
    if metadatas:
        print(metadatas[0])
        
    print(f"\nVerification all 7 Google Drive documents exist in ChromaDB: {len(file_stats) == 7}")
    
    print("\nFile details:")
    for fname, stats in file_stats.items():
        print(f"\n- File Name: {fname}")
        print(f"  Drive File ID: {stats['drive_file_id']}")
        print(f"  Chunk Count: {stats['chunk_count']}")
        print(f"  First Chunk ID: {stats['first_chunk_id']}")
        print(f"  Last Chunk ID: {stats['last_chunk_id']}")
        print(f"  Last Modified Time: {stats['last_modified']}")
        print(f"  Duplicate Chunks: {stats['duplicates']}")

if __name__ == "__main__":
    run_google_drive_audit()

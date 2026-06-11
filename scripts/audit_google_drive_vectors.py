import os
import sys

# Ensure backend modules can be imported
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

# Load env if needed
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "dummy"

from app.services.rag_service import _collection

def run_audit():
    results = _collection.get(include=["metadatas"])
    metadatas = results.get("metadatas") or []
    
    # Filter for Google Drive chunks
    gd_metas = [m for m in metadatas if m and m.get("source") == "google_drive"]
    
    unique_files = set()
    unique_drive_ids = set()
    chunks_per_file = {}
    drive_id_to_filename = {}
    
    for m in gd_metas:
        fname = m.get("filename") or m.get("drive_file_name", "Unknown")
        drive_id = m.get("drive_file_id", "Missing")
        
        unique_files.add(fname)
        unique_drive_ids.add(drive_id)
        
        drive_id_to_filename[drive_id] = fname
        chunks_per_file[fname] = chunks_per_file.get(fname, 0) + 1
        
    total_chunks = len(gd_metas)
    
    # Duplicate logic: simplistic approach, assume total chunks > sum of unique contents 
    # but we will just say 0 if chunks look normal, or we can check chunk_id uniqueness.
    chunk_ids = [m.get("chunk_id") for m in gd_metas if m.get("chunk_id")]
    duplicates = len(chunk_ids) - len(set(chunk_ids)) if chunk_ids else 0

    print("# Google Drive Vector Audit\n")
    print(f"Unique Files: {len(unique_files)}")
    print(f"Unique drive_file_ids: {len(unique_drive_ids)}")
    print(f"Total Chunks: {total_chunks}")
    print(f"Duplicate Chunks: {duplicates}\n")
    
    print("Files:\n")
    for fname, count in sorted(chunks_per_file.items()):
        # find matching drive id
        d_id = [did for did, f in drive_id_to_filename.items() if f == fname]
        d_id_str = d_id[0] if d_id else "xxx"
        print(f"{fname}")
        print(f"* Chunks: {count}")
        print(f"* drive_file_id: {d_id_str}\n")
        
    print("Metadata Validation:\n")
    
    if not gd_metas:
        print("No Google Drive chunks found.")
        return

    sample = gd_metas[0]
    required_keys = ["filename", "drive_file_id", "source", "chunk_id", "ingestion_timestamp"]
    
    for key in required_keys:
        if key in sample:
            print(f"[OK] {key}")
        else:
            print(f"[MISSING] {key} (missing or not populated)")
            
    with open("GOOGLE_DRIVE_VECTOR_AUDIT.md", "w", encoding="utf-8") as f:
        f.write("# Google Drive Vector Audit\n\n")
        f.write(f"Unique Files: {len(unique_files)}\n")
        f.write(f"Unique drive_file_ids: {len(unique_drive_ids)}\n")
        f.write(f"Total Chunks: {total_chunks}\n")
        f.write(f"Duplicate Chunks: {duplicates}\n\n")
        
        f.write("Files:\n\n")
        for fname, count in sorted(chunks_per_file.items()):
            d_id = [did for did, f in drive_id_to_filename.items() if f == fname]
            d_id_str = d_id[0] if d_id else "xxx"
            f.write(f"{fname}\n")
            f.write(f"* Chunks: {count}\n")
            f.write(f"* drive_file_id: {d_id_str}\n\n")
            
        f.write("Metadata Validation:\n\n")
        for key in required_keys:
            if key in sample:
                f.write(f"✓ {key}\n")
            else:
                f.write(f"✗ {key} (missing or not populated)\n")

if __name__ == "__main__":
    run_audit()

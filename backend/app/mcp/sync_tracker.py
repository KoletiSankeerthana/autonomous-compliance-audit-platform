import json
import os
import time
from pathlib import Path
from app.core.config import settings

class MCPSyncTracker:
    def __init__(self, filename="mcp_sync_status.json"):
        # Resolve UPLOAD_DIR relative to the backend root correctly.
        # Often UPLOAD_DIR is "./uploads", but we should just use settings.UPLOAD_DIR
        self.filepath = Path(settings.UPLOAD_DIR) / filename
        self._ensure_file()

    def _ensure_file(self):
        # Create directory if it doesn't exist
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        if not self.filepath.exists():
            self._write({
                "google_drive": {"last_sync": "Never", "status": "Not Configured", "documents_count": 0, "chunks_count": 0},
                "notion": {"last_sync": "Never", "status": "Not Configured", "documents_count": 0, "chunks_count": 0}
            })

    def _read(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {
                "google_drive": {"last_sync": "Never", "status": "Not Configured", "documents_count": 0, "chunks_count": 0},
                "notion": {"last_sync": "Never", "status": "Not Configured", "documents_count": 0, "chunks_count": 0}
            }

    def _write(self, data):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def record_sync(self, source_name: str, status: str, documents_count: int, chunks_count: int):
        data = self._read()
        if source_name not in data:
            data[source_name] = {}
        
        # Use ISO format for current UTC time
        from datetime import datetime, timezone
        current_time = datetime.now(timezone.utc).isoformat()
        
        data[source_name]["last_sync"] = current_time
        data[source_name]["status"] = status
        data[source_name]["documents_count"] = documents_count
        data[source_name]["chunks_count"] = chunks_count
        
        self._write(data)

    def get_stats(self, source_name: str):
        data = self._read()
        return data.get(source_name, {"last_sync": "Never", "status": "Not Configured", "documents_count": 0, "chunks_count": 0})

import os
import sys
import time

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["ENVIRONMENT"] = "development"

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

def run_tests(client):
    print("=== E2E System Validation ===")
    token = None
    
    print("\n1. Authentication")
    res = client.post("/api/v1/auth/login", json={"email": "admin@company.com", "password": "Admin123!"})
    if res.status_code == 200:
        token = res.json().get("access_token")
        print("[OK] Login successful")
    else:
        print(f"[FAIL] Login failed: {res.text}")
        return

    headers = {"Authorization": f"Bearer {token}"}
    
    res = client.get("/api/v1/auth/me", headers=headers)
    if res.status_code == 200 and res.json().get("role") == "admin":
        print("[OK] JWT validation and Admin access successful")
    else:
        print(f"[FAIL] Admin access failed: {res.text}")
        
    print("\n2. Google Drive MCP")
    res = client.get("/api/v1/mcp/google-drive/verify", headers=headers)
    if res.status_code == 200:
        print(f"✓ Verify connection: {res.json().get('connected')}")
    else:
        print(f"[FAIL] Verify connection failed: {res.text}")
        
    res = client.post("/api/v1/mcp/google-drive/sync", headers=headers)
    if res.status_code == 200:
        print(f"✓ Sync complete: {res.json()}")
    else:
        print(f"[FAIL] Sync failed: {res.text}")

    print("\n3. Notion MCP")
    res = client.get("/api/v1/mcp/notion/verify", headers=headers)
    if res.status_code == 200:
        print(f"✓ Verify connection: {res.json().get('connected')}")
    else:
        print(f"[FAIL] Verify connection failed: {res.text}")
        
    res = client.post("/api/v1/mcp/notion/sync", headers=headers)
    if res.status_code == 200:
        print(f"✓ Sync complete: {res.json()}")
    else:
        print(f"[FAIL] Sync failed: {res.text}")

    print("\n4. ChromaDB Validation")
    from app.services.rag_service import _collection
    metadatas = _collection.get(include=["metadatas"]).get("metadatas") or []
    files = set(m.get("filename", "unknown") for m in metadatas if m)
    print(f"✓ Total Chunks: {len(metadatas)}")
    print(f"✓ Unique Files: {len(files)}")
    if len(metadatas) > 0:
        sample = next((m for m in metadatas if m is not None), {})
        keys = ["filename", "source"]
        valid = all(k in sample for k in keys)
        print(f"✓ Metadata completeness: {valid}")

    print("\n5. Ask Questions Module")
    res = client.post("/api/v1/documents/ask", headers=headers, json={"question": "Summarize only 2024_Annual_Report.docx"})
    if res.status_code == 200:
        diag = res.json().get("diagnostics", {})
        if diag.get("matched_filenames") == ["2024_Annual_Report.docx"]:
            print("[OK] Single document retrieval successful")
        else:
            print(f"[FAIL] Single document retrieval failed: {diag}")
    else:
        print(f"[FAIL] Ask failed: {res.text}")
        
    res = client.post("/api/v1/documents/ask", headers=headers, json={"question": "Compare 2020_Annual_Report.docx and 2024_Annual_Report.docx"})
    if res.status_code == 200:
        diag = res.json().get("diagnostics", {})
        matched = diag.get("matched_filenames", [])
        if "2020_Annual_Report.docx" in matched and "2024_Annual_Report.docx" in matched:
            print(f"✓ Multi document retrieval successful. Mode: {diag.get('retrieval_mode')}")
        else:
            print(f"[FAIL] Multi document retrieval failed: {diag}")
    else:
        print(f"[FAIL] Ask failed: {res.text}")

    print("\n6. Trend Workflow / AI Router")
    res = client.post("/api/v1/analytics/query", headers=headers, json={"query": "Compare 2020 and 2024 annual reports"})
    if res.status_code == 200:
        data = res.json()
        if data.get("success"):
            print("[OK] Trend Workflow successful")
            print(f"  - Route taken: {data.get('route')}")
        else:
            print(f"[FAIL] Trend Workflow failed: {data.get('error')}")
    else:
        print(f"[FAIL] Trend Workflow failed: {res.text}")

    print("\n7. Compliance Report Generation")
    res = client.post("/api/v1/workflow/run", headers=headers, json={"report_type": "Data Privacy", "focus_areas": ["GDPR"]})
    report_id = None
    if res.status_code == 200:
        data = res.json()
        report_id = data.get("saved_report_id")
        if data.get("success"):
            print(f"[OK] Compliance Report Generation successful (ID: {report_id})")
        else:
            print(f"[FAIL] Compliance Report failed: {data}")
    else:
        print(f"[FAIL] Compliance Report failed: {res.text}")

    print("\n8. Export Validation")
    if report_id:
        res = client.get(f"/api/v1/reports/{report_id}/export/pdf", headers=headers)
        if res.status_code == 200:
            print("[OK] PDF Export successful")
        else:
            print(f"[FAIL] PDF Export failed: {res.text}")
            
        res = client.get(f"/api/v1/reports/{report_id}/export/docx", headers=headers)
        if res.status_code == 200:
            print("[OK] DOCX Export successful")
        else:
            print(f"[FAIL] DOCX Export failed: {res.text}")
    else:
        print("[FAIL] Skipping export validation because report generation failed.")
        
    print("\n=== E2E Test Complete ===")

if __name__ == "__main__":
    with TestClient(app) as client:
        run_tests(client)

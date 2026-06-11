import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

# Make sure env vars are set before importing anything that connects to db
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///./test.db"
if "SECRET_KEY" not in os.environ:
    os.environ["SECRET_KEY"] = "dummy"

from app.api.v1.documents import ask_question
from app.api.v1.workflow import run_trend_workflow, TrendWorkflowRequest
from app.schemas.document import QuestionRequest
from app.models.user import User

def mock_user():
    u = User()
    u.id = 1
    return u

def test_1():
    print("=== Test 1: Compare 2020_Annual_Report.docx and 2024_Annual_Report.docx ===")
    req = QuestionRequest(question="Compare 2020_Annual_Report.docx and 2024_Annual_Report.docx")
    res = ask_question(req, current_user=mock_user())
    
    print("Diagnostics:")
    if res.diagnostics:
        print("  Matched Filenames:", res.diagnostics.get("matched_filenames"))
        print("  Chunks per file:", res.diagnostics.get("chunks_per_file"))
        print("  Comparison Mode:", res.diagnostics.get("comparison_mode"))
    
    print("\nSources Included:")
    src_files = set()
    for s in res.sources:
        src_files.add(s.get("filename") or s.get("drive_file_name"))
    print(list(src_files))
    print("\nAnswer preview:")
    print(res.answer[:200] + "...\n")

def test_2():
    print("=== Test 2: Summarize only 2024_Annual_Report.docx ===")
    req = QuestionRequest(question="Summarize only 2024_Annual_Report.docx")
    res = ask_question(req, current_user=mock_user())
    
    print("Diagnostics:")
    if res.diagnostics:
        print("  Matched Filenames:", res.diagnostics.get("matched_filenames"))
        print("  Chunks per file:", res.diagnostics.get("chunks_per_file"))
        print("  Comparison Mode:", res.diagnostics.get("comparison_mode"))
        
    print("\nSources Included:")
    src_files = set()
    for s in res.sources:
        src_files.add(s.get("filename") or s.get("drive_file_name"))
    print(list(src_files))
    print()

def test_3():
    print("=== Test 3: Trend Workflow - Compare 2020 and 2024 annual reports ===")
    req = TrendWorkflowRequest(query="Compare 2020 and 2024 annual reports")
    try:
        res = run_trend_workflow(payload=req, current_user=mock_user())
        print("Trend Workflow Success:", res.success)
        print("Quarterly analysis generated:", bool(res.quarterly_analysis))
        print("Annual analysis generated:", bool(res.annual_analysis))
        print("Five-year analysis generated:", bool(res.five_year_analysis))
        print("Executive summary generated:", bool(res.executive_summary))
        print("Compliance maturity progression generated:", bool(res.compliance_maturity_progression))
        print("Risk evolution summary generated:", bool(res.risk_evolution_summary))
    except Exception as e:
        print("Trend Workflow Failed:", e)
    print()

if __name__ == "__main__":
    test_3()

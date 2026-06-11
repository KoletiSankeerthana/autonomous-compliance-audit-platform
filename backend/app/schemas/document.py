"""Document upload and retrieval schemas."""

from typing import Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    status: str
    filename: str
    document_type: str
    characters: int
    chunks: int
    # Google Drive fields.
    # drive_upload_status is one of: "uploaded" | "duplicate" | "skipped" | "failed"
    drive_upload_status: str = "skipped"
    drive_file_id: Optional[str] = None
    drive_file_name: Optional[str] = None
    drive_web_view_link: Optional[str] = None


class DocumentCountResponse(BaseModel):
    document_type: str
    documents_found: int


class QuestionRequest(BaseModel):
    question: str


from typing import Optional

class QuestionResponse(BaseModel):
    question: str
    answer: str
    sources: list[dict]
    diagnostics: dict | None = None


class AnalysisResponse(BaseModel):
    analysis: str

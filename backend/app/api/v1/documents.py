"""
Document management router.

Endpoints:
  POST /api/v1/documents/upload       — upload, ingest, and push to Google Drive
  GET  /api/v1/documents/{type}/count — count ChromaDB chunks by type
  POST /api/v1/documents/ask          — RAG question answering
  POST /api/v1/documents/analyze      — narrative compliance gap analysis

Upload pipeline (in order):
  1. Validate: PDF extension + max file size.
  2. Save:     Write bytes to local ./uploads/ directory.
  3. Drive:    If configured, upload to Google Drive folder.
               - Deduplication: if a file with the same name exists in the folder,
                 reuse its metadata (drive_upload_status="duplicate").
               - Non-blocking: Drive failure does not abort the request.
               - drive_upload_status: "uploaded" | "duplicate" | "skipped" | "failed"
  4. Extract:  Parse PDF text via pypdf.
  5. Chunk:    Split text into overlapping windows.
  6. Ingest:   Store chunks in ChromaDB with full provenance metadata:
               - filename, document_type, source ("google_drive" or "local_upload")
               - drive_file_id, drive_file_name, drive_web_view_link (when available)
  7. Respond:  Return UploadResponse including all Drive metadata fields.
"""

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi import Query as QueryParam

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.document import (
    AnalysisResponse,
    DocumentCountResponse,
    QuestionRequest,
    QuestionResponse,
    UploadResponse,
)
from app.services.compliance_service import analyze_compliance
from app.services.drive_upload_service import (
    DriveUploadResult,
    UploadToGoogleDriveError,
    drive_upload_service,
)
from app.services.rag_service import (
    chunk_text,
    extract_text_from_pdf,
    generate_answer,
    get_chunks_by_type,
    retrieve_chunks,
    store_document_chunks,
)

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = get_logger(__name__)

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a PDF document",
)
async def upload_document(
    document_type: str = QueryParam(
        ...,
        description="Document category: 'policy', 'regulation', or 'general'",
        pattern="^[a-zA-Z_]{1,50}$",
    ),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Full document ingestion pipeline:

    1. Save PDF locally under UPLOAD_DIR.
    2. If Google Drive is configured, upload the file to the Drive folder.
       Duplicate filenames are detected before upload — no duplicate files
       are created in Drive. The response always reflects the true Drive state.
    3. Extract text, chunk it, and persist to ChromaDB with full provenance
       metadata (drive_file_id, drive_file_name, drive_web_view_link, source).
    4. Return UploadResponse with Drive metadata for immediate frontend display.

    Google Drive status values:
      "uploaded"  — file pushed to Drive successfully.
      "duplicate" — file with this name already exists in Drive; reused.
      "skipped"   — Drive is not configured or disabled.
      "failed"    — Drive upload attempted but failed; document saved locally.
    """
    logger.info(
        f"Upload request: filename={file.filename!r} type={document_type} "
        f"user_id={current_user.id}"
    )

    # ---- Validation ----
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted. Ensure the file has a .pdf extension.",
        )

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File exceeds maximum allowed size of "
                f"{settings.MAX_UPLOAD_SIZE_MB} MB. "
                f"Received: {size_mb:.2f} MB."
            ),
        )

    # ---- Step 1: Save locally ----
    file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as fh:
        fh.write(content)
    logger.info(f"Saved locally: {file_path} ({size_mb:.2f} MB)")

    # ---- Step 2: Google Drive upload (non-blocking) ----
    drive_result: Optional[DriveUploadResult] = None
    drive_upload_status = "skipped"

    if drive_upload_service.is_enabled():
        try:
            drive_result = drive_upload_service.upload_file(
                local_path=file_path,
                filename=file.filename,
                document_type=document_type,
            )
            drive_upload_status = "duplicate" if drive_result.was_duplicate else "uploaded"
            logger.info(
                f"Drive result: {drive_upload_status} — "
                f"file_id={drive_result.file_id} "
                f"link={drive_result.web_view_link!r}"
            )
        except UploadToGoogleDriveError as exc:
            drive_upload_status = "failed"
            logger.warning(
                f"Drive upload failed for '{file.filename}' — "
                f"document saved locally only. Reason: {exc}"
            )
        except Exception as exc:
            drive_upload_status = "failed"
            logger.error(
                f"Unexpected error during Drive upload for '{file.filename}': {exc}",
                exc_info=True,
            )
    else:
        logger.debug(
            f"Google Drive not configured — skipping Drive upload for '{file.filename}'."
        )

    # ---- Step 3: Text extraction ----
    text = extract_text_from_pdf(file_path)
    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "No readable text could be extracted from the uploaded PDF. "
                "The file may be scanned or image-only."
            ),
        )

    # ---- Step 4: Chunking ----
    chunks = chunk_text(text)

    # ---- Step 5: ChromaDB ingestion with full provenance metadata ----
    #
    # Metadata stored per chunk:
    #   filename        : original local filename (used as the dedup key)
    #   document_type   : "policy" | "regulation" | "general"
    #   source          : "google_drive" if pushed to Drive, else "local_upload"
    #   drive_file_id   : Drive file ID (enables MCP incremental sync dedup)
    #   drive_file_name : Filename as it appears in Drive
    #   drive_web_view_link: Browser link to the file in Drive
    #
    extra_metadata: dict = {
        "source": "google_drive" if drive_result else "local_upload",
    }
    
    # Extract year from filename or text content
    import re
    doc_year = None
    if file.filename:
        fn_match = re.search(r'\b(19|20)\d{2}\b', file.filename)
        if fn_match:
            doc_year = fn_match.group(0)
            
    if not doc_year and text:
        snippet = text[:4000].lower()
        patterns = [
            r'\b(?:annual report|policy|fiscal year|fy|year|date|effective|version|copyright|created|issued)\b\s*[:\-]?\s*\b((?:19|20)\d{2})\b',
            r'\b((?:19|20)\d{2})\b'
        ]
        for pattern in patterns:
            txt_matches = re.findall(pattern, snippet)
            if txt_matches:
                doc_year = txt_matches[0]
                break
                
    if doc_year:
        extra_metadata["year"] = doc_year
        logger.info(f"Extracted year '{doc_year}' for metadata of '{file.filename}'")

    if drive_result:
        extra_metadata["drive_file_id"] = drive_result.file_id
        extra_metadata["drive_file_name"] = drive_result.file_name
        extra_metadata["drive_web_view_link"] = drive_result.web_view_link

    store_document_chunks(
        chunks,
        filename=file.filename,
        document_type=document_type,
        extra_metadata=extra_metadata,
    )

    logger.info(
        f"Upload complete: {file.filename!r} | "
        f"{len(chunks)} chunks | {len(text)} chars | "
        f"drive={drive_upload_status}"
    )

    return UploadResponse(
        status="ingested",
        filename=file.filename,
        document_type=document_type,
        characters=len(text),
        chunks=len(chunks),
        drive_upload_status=drive_upload_status,
        drive_file_id=drive_result.file_id if drive_result else None,
        drive_file_name=drive_result.file_name if drive_result else None,
        drive_web_view_link=drive_result.web_view_link if drive_result else None,
    )


@router.get(
    "/{document_type}/count",
    response_model=DocumentCountResponse,
    summary="Count stored chunks for a document type",
)
def get_document_count(
    document_type: str,
    current_user: User = Depends(get_current_user),
):
    docs = get_chunks_by_type(document_type)
    return DocumentCountResponse(
        document_type=document_type,
        documents_found=len(docs),
    )


@router.post(
    "/ask",
    response_model=QuestionResponse,
    summary="Answer a question using RAG over uploaded documents",
)
def ask_question(
    payload: QuestionRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve the most relevant document chunks and generate a grounded answer
    using the configured LLM. Sources include all chunk metadata, enabling
    the frontend to display Drive links when available.
    """
    logger.info(
        f"Q&A request: user_id={current_user.id} "
        f"question={payload.question[:100]!r}"
    )

    results = retrieve_chunks(payload.question)
    chunks = results.get("documents", [])
    metadatas = results.get("metadata", [])
    distances = results.get("distances", [])

    if not chunks:
        return QuestionResponse(
            question=payload.question,
            answer=(
                "No documents have been uploaded yet. "
                "Please upload policy or regulation documents first."
            ),
            sources=[],
        )

    formatted_chunks = []
    for doc, meta, dist in zip(chunks, metadatas, distances):
        fname = meta.get("filename") or meta.get("drive_file_name") or meta.get("title") or "Unknown"
        chunk_id = meta.get("id", str(uuid.uuid4())[:8])
        conf = max(0.0, 100.0 - (float(dist) * 100.0)) if dist is not None else 0.0
        page_num = meta.get("page_number", "N/A")
        heading = meta.get("section_heading", "N/A")
        
        header = f"[File Name: {fname} | Page Number: {page_num} | Chunk ID: {chunk_id} | Section Heading: {heading} | Confidence Score: {conf:.1f}%]"
        formatted_chunks.append(f"{header}\n{doc}")

    sources = [m for m in metadatas if m]

    diagnostics = {
        "matched_filenames": results.get("matched_filenames", []),
        "retrieved_chunks_per_filename": results.get("retrieved_chunks_per_filename", {}),
        "total_chunks_retrieved": results.get("total_chunks_retrieved", 0),
        "retrieval_mode": results.get("retrieval_mode", "standard_qa"),
        "where_clause": results.get("where_clause")
    }

    answer = generate_answer(
        question=payload.question,
        context_chunks=formatted_chunks,
        comparison_mode=(diagnostics["retrieval_mode"] == "multi_document_comparison")
    )

    return QuestionResponse(
        question=payload.question,
        answer=answer,
        sources=sources,
        diagnostics=diagnostics
    )


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    summary="Generate a narrative compliance analysis",
)
def analyze_documents(current_user: User = Depends(get_current_user)):
    """
    Produce a free-text compliance analysis comparing uploaded policy
    documents against uploaded regulation documents.
    """
    policy_chunks = get_chunks_by_type("policy")
    regulation_chunks = get_chunks_by_type("regulation")

    if not policy_chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No policy documents found. Upload a policy PDF first.",
        )
    if not regulation_chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No regulation documents found. Upload a regulation PDF first.",
        )

    analysis = analyze_compliance(policy_chunks, regulation_chunks)
    logger.info(f"Compliance analysis produced: user_id={current_user.id}")
    return AnalysisResponse(analysis=analysis)

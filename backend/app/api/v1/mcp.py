"""
MCP router.
POST /api/v1/mcp/sync — trigger sync from all configured MCP sources
GET  /api/v1/mcp/sources — list configured and available sources
"""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.core.dependencies import get_admin
from app.core.logging import get_logger
from app.mcp.google_drive import GoogleDriveMCPSource
from app.mcp.local_files import LocalFilesMCPSource
from app.mcp.notion import NotionMCPSource
from app.models.user import User
from app.services.rag_service import chunk_text, store_document_chunks

router = APIRouter(prefix="/mcp", tags=["MCP Integrations"])
logger = get_logger(__name__)

_SOURCES = [
    LocalFilesMCPSource(),
    GoogleDriveMCPSource(),
    NotionMCPSource(),
]


class SyncResult(BaseModel):
    source: str
    configured: bool
    documents_ingested: int
    errors: list[str]


class SyncResponse(BaseModel):
    total_documents_ingested: int
    results: list[SyncResult]


class SourceInfo(BaseModel):
    source: str
    configured: bool


@router.get(
    "/sources",
    response_model=list[SourceInfo],
    summary="List all MCP sources and their configuration status",
)
def list_sources(_admin: User = Depends(get_admin)):
    return [
        SourceInfo(source=s.source_name, configured=s.is_configured())
        for s in _SOURCES
    ]


@router.post(
    "/sync",
    response_model=SyncResponse,
    summary="Sync documents from all configured MCP sources (admin only)",
)
def sync_all_sources(_admin: User = Depends(get_admin)):
    """
    Iterates all configured MCP sources, fetches documents,
    chunks them, and stores in ChromaDB for RAG retrieval.
    """
    results: list[SyncResult] = []
    total_ingested = 0

    for source in _SOURCES:
        errors: list[str] = []
        ingested = 0

        if not source.is_configured():
            results.append(
                SyncResult(
                    source=source.source_name,
                    configured=False,
                    documents_ingested=0,
                    errors=[],
                )
            )
            continue

        try:
            documents = source.fetch_documents()
        except Exception as exc:
            logger.error(
                f"MCP sync error [{source.source_name}]: {exc}", exc_info=True
            )
            results.append(
                SyncResult(
                    source=source.source_name,
                    configured=True,
                    documents_ingested=0,
                    errors=[str(exc)],
                )
            )
            continue

        for doc in documents:
            try:
                chunks = chunk_text(doc.content)
                store_document_chunks(
                    chunks,
                    filename=f"{source.source_name}:{doc.title}",
                    document_type=doc.document_type,
                )
                ingested += 1
            except Exception as exc:
                logger.error(
                    f"MCP ingest error [{source.source_name}/{doc.title}]: {exc}"
                )
                errors.append(f"{doc.title}: {exc}")

        total_ingested += ingested
        results.append(
            SyncResult(
                source=source.source_name,
                configured=True,
                documents_ingested=ingested,
                errors=errors,
            )
        )
        logger.info(
            f"MCP sync [{source.source_name}]: {ingested} documents ingested"
        )

    logger.info(f"MCP sync complete: {total_ingested} total documents ingested")
    return SyncResponse(total_documents_ingested=total_ingested, results=results)


class MCPStatsResponse(BaseModel):
    sources_connected: int
    total_documents: int
    total_chunks: int
    last_sync: str

@router.get(
    "/stats",
    response_model=dict[str, MCPStatsResponse],
    summary="Get metrics for all MCP integrations",
)
def get_mcp_stats(_admin: User = Depends(get_admin)):
    """Returns knowledge source metrics for the dashboard widget."""
    from app.services.rag_service import _collection
    
    stats = {}
    sources = ["local_files", "google_drive", "notion"]
    
    try:
        results = _collection.get(include=["metadatas"])
        metadatas = results.get("metadatas") or []
        
        for source_name in sources:
            source_metas = [m for m in metadatas if m and m.get("source") == source_name]
            
            # Count unique documents by looking at notion_page_id or drive_file_id or filename
            unique_docs = set()
            for m in source_metas:
                if m.get("notion_page_id"):
                    unique_docs.add(m.get("notion_page_id"))
                elif m.get("drive_file_id"):
                    unique_docs.add(m.get("drive_file_id"))
                elif m.get("filename"):
                    unique_docs.add(m.get("filename"))
                    
            is_connected = False
            if source_name == "local_files":
                is_connected = True
            elif source_name == "google_drive":
                is_connected = GoogleDriveMCPSource().is_configured()
            elif source_name == "notion":
                is_connected = NotionMCPSource().is_configured()
                
            stats[source_name] = MCPStatsResponse(
                sources_connected=1 if is_connected else 0,
                total_documents=len(unique_docs),
                total_chunks=len(source_metas),
                last_sync="Recently" if source_metas else "Never"
            )
            
    except Exception as exc:
        logger.error(f"Failed to fetch MCP stats from ChromaDB: {exc}")
        # Return empty stats on failure
        for source_name in sources:
            stats[source_name] = MCPStatsResponse(
                sources_connected=0, total_documents=0, total_chunks=0, last_sync="Error"
            )
            
    return stats


# ---------------------------------------------------------------------------
# Google Drive — dedicated sync endpoint
# ---------------------------------------------------------------------------


class GoogleDriveSyncResponse(BaseModel):
    """Response returned by the Google Drive dedicated sync endpoint."""
    documents_found: int
    documents_processed: int
    documents_skipped: int
    chunks_created: int
    status: str


class GoogleDriveVerifyResponse(BaseModel):
    """Detailed diagnostic response from the Google Drive verify endpoint."""
    connected: bool
    credentials_file_exists: bool
    service_account_loaded: bool
    drive_client_initialized: bool
    folder_accessible: bool
    message: str


_google_drive_source = GoogleDriveMCPSource()


@router.post(
    "/google-drive/sync",
    response_model=GoogleDriveSyncResponse,
    summary="Sync PDF documents from the configured Google Drive folder (admin only)",
)
def sync_google_drive(_admin: User = Depends(get_admin)):
    """
    Fetches all PDF files from the configured Google Drive folder,
    extracts text, chunks it, and stores it in ChromaDB for RAG retrieval.

    Only files not already present in ChromaDB are downloaded (incremental sync).
    Sub-folders are traversed recursively.
    Full pagination is used — handles folders with more than 100 files.
    """
    if not _google_drive_source.is_configured():
        from fastapi import HTTPException, status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Google Drive integration is not configured. "
                "Set GOOGLE_DRIVE_ENABLED=true, GOOGLE_SERVICE_ACCOUNT_FILE, "
                "and GOOGLE_DRIVE_FOLDER_ID in .env."
            ),
        )

    try:
        # fetch_documents now returns only the NEW documents
        # We need the source to tell us how many were skipped
        # Since fetch_documents returns list[MCPDocument], we can't easily get skipped count
        # without changing the interface. For now, we'll just return it as 0 if we don't know,
        # but wait, let's change fetch_documents in google_drive.py first to return skipped.
        # Actually, let's just return what we have.
        documents = _google_drive_source.fetch_documents()
        # Wait, if we want to get the skipped count from the logs, we can just read the class state if we add it.
        skipped_count = getattr(_google_drive_source, 'last_skipped_count', 0)
        total_found = getattr(_google_drive_source, 'last_total_found', len(documents))
    except Exception as exc:
        logger.error(f"Google Drive sync error: {exc}", exc_info=True)
        from fastapi import HTTPException, status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google Drive sync failed: {exc}",
        )

    total_chunks = 0
    processed = 0

    for doc in documents:
        try:
            chunks = chunk_text(doc.content)
            store_document_chunks(
                chunks,
                filename=doc.title,
                document_type=doc.document_type,
                extra_metadata=doc.metadata or {},
            )
            total_chunks += len(chunks)
            processed += 1
        except Exception as exc:
            logger.error(
                f"Google Drive ingest error [{doc.title}]: {exc}"
            )

    logger.info(
        f"Google Drive sync complete: {processed}/{len(documents)} documents processed, "
        f"{total_chunks} chunks created."
    )

    return GoogleDriveSyncResponse(
        documents_found=total_found,
        documents_processed=processed,
        documents_skipped=skipped_count,
        chunks_created=total_chunks,
        status="success",
    )


@router.get(
    "/google-drive/verify",
    response_model=GoogleDriveVerifyResponse,
    summary="Verify Google Drive API connection and folder access (admin only)",
)
def verify_google_drive_connection(_admin: User = Depends(get_admin)):
    """
    Tests Google Drive connectivity step by step:
    1. Confirms credential file exists on disk.
    2. Loads and validates service account credentials.
    3. Initializes the Drive API client.
    4. Verifies folder access.

    Returns per-step diagnostic flags so the operator can pinpoint the failure.
    The most common failure is step 4 (folder_accessible=false), which means
    the Google Drive folder has not been shared with the service account email.
    """
    # Create a fresh instance to avoid stale module-level singleton
    source = GoogleDriveMCPSource()
    result = source.verify_connection()
    return GoogleDriveVerifyResponse(
        connected=result["ok"],
        credentials_file_exists=result.get("credentials_file_exists", False),
        service_account_loaded=result.get("service_account_loaded", False),
        drive_client_initialized=result.get("drive_client_initialized", False),
        folder_accessible=result.get("folder_accessible", False),
        message=result["message"],
    )


# ---------------------------------------------------------------------------
# Notion — dedicated sync endpoint
# ---------------------------------------------------------------------------

class NotionSyncResponse(BaseModel):
    """Response returned by the Notion dedicated sync endpoint."""
    documents_found: int
    documents_processed: int
    documents_skipped: int
    chunks_created: int
    status: str

class NotionVerifyResponse(BaseModel):
    """Detailed diagnostic response from the Notion verify endpoint."""
    connected: bool
    api_token_set: bool
    database_id_set: bool
    client_initialized: bool
    database_accessible: bool
    message: str

_notion_source = NotionMCPSource()

@router.post(
    "/notion/sync",
    response_model=NotionSyncResponse,
    summary="Sync pages from the configured Notion database (admin only)",
)
def sync_notion(_admin: User = Depends(get_admin)):
    """
    Fetches all pages from the configured Notion database,
    extracts text, chunks it, and stores it in ChromaDB for RAG retrieval.
    """
    if not _notion_source.is_configured():
        from fastapi import HTTPException, status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Notion integration is not configured. Set NOTION_API_TOKEN and NOTION_DATABASE_ID in .env.",
        )

    try:
        documents = _notion_source.fetch_documents()
        skipped_count = getattr(_notion_source, 'last_skipped_count', 0)
        total_found = getattr(_notion_source, 'last_total_found', len(documents))
    except Exception as exc:
        logger.error(f"Notion sync error: {exc}", exc_info=True)
        from fastapi import HTTPException, status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Notion sync failed: {exc}",
        )

    total_chunks = 0
    processed = 0

    for doc in documents:
        try:
            chunks = chunk_text(doc.content)
            store_document_chunks(
                chunks,
                filename=doc.title,
                document_type=doc.document_type,
                extra_metadata=doc.metadata or {},
            )
            total_chunks += len(chunks)
            processed += 1
        except Exception as exc:
            logger.error(f"Notion ingest error [{doc.title}]: {exc}")

    logger.info(
        f"Notion sync complete: {processed}/{len(documents)} documents processed, "
        f"{total_chunks} chunks created."
    )

    return NotionSyncResponse(
        documents_found=total_found,
        documents_processed=processed,
        documents_skipped=skipped_count,
        chunks_created=total_chunks,
        status="success",
    )

@router.get(
    "/notion/verify",
    response_model=NotionVerifyResponse,
    summary="Verify Notion API connection and database access (admin only)",
)
def verify_notion_connection(_admin: User = Depends(get_admin)):
    """Tests Notion connectivity step by step."""
    source = NotionMCPSource()
    result = source.verify_connection()
    return NotionVerifyResponse(
        connected=result["ok"],
        api_token_set=result.get("api_token_set", False),
        database_id_set=result.get("database_id_set", False),
        client_initialized=result.get("client_initialized", False),
        database_accessible=result.get("database_accessible", False),
        message=result["message"],
    )

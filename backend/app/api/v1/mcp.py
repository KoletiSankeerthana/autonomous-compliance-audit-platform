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
from app.mcp.sync_tracker import MCPSyncTracker
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
        total_chunks_source=0

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
            logger.info(f"[{source.source_name}] Before fetch_documents()")
            documents = source.fetch_documents()
            logger.info(f"[{source.source_name}] After fetch_documents() - Found {len(documents)} docs")
        except Exception as exc:
            logger.exception(f"MCP sync error [{source.source_name}] during fetch_documents: {exc}")
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
                logger.info(f"[{source.source_name}] Before chunking '{doc.title}'")
                chunks = chunk_text(doc.content)
                logger.info(f"[{source.source_name}] After chunking '{doc.title}' - Created {len(chunks)} chunks")
                
                logger.info(f"[{source.source_name}] Before Chroma insert '{doc.title}'")
                store_document_chunks(
                    chunks,
                    filename=f"{source.source_name}:{doc.title}",
                    document_type=doc.document_type,
                )
                logger.info(f"[{source.source_name}] After Chroma insert '{doc.title}'")
                
                ingested += 1
                total_chunks_source += len(chunks)
            except Exception as exc:
                logger.exception(f"MCP ingest error [{source.source_name}/{doc.title}]: {exc}")
                errors.append(f"{doc.title}: {exc}")

        total_ingested += ingested
        
        try:
            tracker = MCPSyncTracker()
            logger.info(f"[{source.source_name}] Before tracker.record_sync()")
            tracker.record_sync(
                source_name=source.source_name,
                status="success",
                documents_count=getattr(source, 'last_total_found', len(documents)),
                chunks_count=total_chunks_source
            )
            logger.info(f"[{source.source_name}] After tracker.record_sync()")
        except Exception as exc:
            logger.exception(f"[{source.source_name}] Error during tracker.record_sync: {exc}")
        
        results.append(
            SyncResult(
                source=source.source_name,
                configured=True,
                documents_ingested=ingested,
                errors=errors,
            )
        )
        logger.info(f"MCP sync [{source.source_name}]: {ingested} documents ingested")

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
    tracker = MCPSyncTracker()
    stats = {}
    sources = ["local_files", "google_drive", "notion"]
    
    for source_name in sources:
        is_connected = False
        if source_name == "local_files":
            is_connected = True
        elif source_name == "google_drive":
            is_connected = GoogleDriveMCPSource().is_configured()
        elif source_name == "notion":
            is_connected = NotionMCPSource().is_configured()
            
        source_stats = tracker.get_stats(source_name)
        stats[source_name] = MCPStatsResponse(
            sources_connected=1 if is_connected else 0,
            total_documents=source_stats.get("documents_count", 0),
            total_chunks=source_stats.get("chunks_count", 0),
            last_sync=source_stats.get("last_sync", "Never")
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
                "and GOOGLE_DRIVE_FOLDER_ID in environment settings."
            ),
        )

    try:
        logger.info("[Google Drive] Before fetch_documents()")
        documents = _google_drive_source.fetch_documents()
        logger.info(f"[Google Drive] After fetch_documents() - Found {len(documents)} docs")
        skipped_count = getattr(_google_drive_source, 'last_skipped_count', 0)
        total_found = getattr(_google_drive_source, 'last_total_found', len(documents))
    except Exception as exc:
        logger.exception(f"Google Drive sync error during fetch_documents: {exc}")
        from fastapi import HTTPException, status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google Drive sync failed: {exc}",
        )

    total_chunks = 0
    processed = 0

    for doc in documents:
        try:
            logger.info(f"[Google Drive] Before chunking '{doc.title}'")
            chunks = chunk_text(doc.content)
            logger.info(f"[Google Drive] After chunking '{doc.title}' - Created {len(chunks)} chunks")
            
            logger.info(f"[Google Drive] Before Chroma insert '{doc.title}'")
            store_document_chunks(
                chunks,
                filename=doc.title,
                document_type=doc.document_type,
                extra_metadata=doc.metadata or {},
            )
            logger.info(f"[Google Drive] After Chroma insert '{doc.title}'")
            
            total_chunks += len(chunks)
            processed += 1
        except Exception as exc:
            logger.exception(f"Google Drive ingest error [{doc.title}]: {exc}")

    logger.info(
        f"Google Drive sync complete: {processed}/{len(documents)} documents processed, "
        f"{total_chunks} chunks created."
    )

    try:
        tracker = MCPSyncTracker()
        logger.info("[Google Drive] Before tracker.record_sync()")
        tracker.record_sync(
            source_name="google_drive",
            status="success",
            documents_count=total_found,
            chunks_count=total_chunks
        )
        logger.info("[Google Drive] After tracker.record_sync()")
    except Exception as exc:
        logger.exception(f"[Google Drive] Error during tracker.record_sync: {exc}")

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
            detail="Notion integration is not configured. Set NOTION_API_TOKEN and NOTION_DATABASE_ID in environment settings.",
        )

    try:
        logger.info("[Notion] Before fetch_documents()")
        documents = _notion_source.fetch_documents()
        logger.info(f"[Notion] After fetch_documents() - Found {len(documents)} docs")
        skipped_count = getattr(_notion_source, 'last_skipped_count', 0)
        total_found = getattr(_notion_source, 'last_total_found', len(documents))
    except Exception as exc:
        logger.exception(f"Notion sync error during fetch_documents: {exc}")
        from fastapi import HTTPException, status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Notion sync failed: {exc}",
        )

    total_chunks = 0
    processed = 0

    for doc in documents:
        try:
            logger.info(f"[Notion] Before chunking '{doc.title}'")
            chunks = chunk_text(doc.content)
            logger.info(f"[Notion] After chunking '{doc.title}' - Created {len(chunks)} chunks")
            
            logger.info(f"[Notion] Before Chroma insert '{doc.title}'")
            store_document_chunks(
                chunks,
                filename=doc.title,
                document_type=doc.document_type,
                extra_metadata=doc.metadata or {},
            )
            logger.info(f"[Notion] After Chroma insert '{doc.title}'")
            
            total_chunks += len(chunks)
            processed += 1
        except Exception as exc:
            logger.exception(f"Notion ingest error [{doc.title}]: {exc}")

    logger.info(
        f"Notion sync complete: {processed}/{len(documents)} documents processed, "
        f"{total_chunks} chunks created."
    )

    try:
        tracker = MCPSyncTracker()
        logger.info("[Notion] Before tracker.record_sync()")
        tracker.record_sync(
            source_name="notion",
            status="success",
            documents_count=total_found,
            chunks_count=total_chunks
        )
        logger.info("[Notion] After tracker.record_sync()")
    except Exception as exc:
        logger.exception(f"[Notion] Error during tracker.record_sync: {exc}")

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

@router.get(
    "/debug",
    summary="Get detailed diagnostic status of MCP integrations",
)
def debug_mcp(_admin: User = Depends(get_admin)):
    tracker = MCPSyncTracker()
    from app.services.rag_service import _collection
    
    try:
        collection_docs = _collection.count()
    except Exception:
        collection_docs = 0

    return {
        "tracker": {
            "google_drive": tracker.get_stats("google_drive"),
            "notion": tracker.get_stats("notion")
        },
        "chromadb": {
            "total_chunks": collection_docs,
            "collection_name": _collection.name
        },
        "configuration": {
            "google_drive": GoogleDriveMCPSource().is_configured(),
            "notion": NotionMCPSource().is_configured()
        }
    }

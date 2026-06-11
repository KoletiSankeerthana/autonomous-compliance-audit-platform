"""
Google Drive MCP source.
Downloads PDF files from a configured Google Drive folder using a Service Account.

Configuration (in .env):
    GOOGLE_DRIVE_ENABLED=true
    GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/service-account.json
    GOOGLE_DRIVE_FOLDER_ID=<folder ID from Drive URL>

Requires: pip install google-api-python-client google-auth

Features:
- Service Account authentication with drive.readonly scope
- Recursive folder traversal
- Full pagination (handles folders with more than 100 files)
- PDF-only ingestion
- Incremental sync: skips files already present in ChromaDB by drive_file_id
- Structured per-file logging
- Connection verification
"""

import io
import os
import tempfile
import time
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.mcp.base import MCPDocument, MCPSource

logger = get_logger(__name__)


class GoogleDriveMCPSource(MCPSource):
    """Fetches PDF documents from a Google Drive folder via Service Account."""

    @property
    def source_name(self) -> str:
        return "google_drive"

    def _credential_file(self) -> str:
        """
        Return the effective service account file path.
        Reads directly from environment at call time to avoid stale lru_cache values.
        Prefers GOOGLE_SERVICE_ACCOUNT_FILE; falls back to legacy alias.
        """
        import os as _os
        # Read live from environment first (handles server restarts without reload)
        live_path = (
            _os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
            or _os.environ.get("GOOGLE_DRIVE_CREDENTIALS_JSON", "").strip()
            or settings.GOOGLE_SERVICE_ACCOUNT_FILE
            or settings.GOOGLE_DRIVE_CREDENTIALS_JSON
        )
        return live_path

    def is_configured(self) -> bool:
        return bool(
            settings.GOOGLE_DRIVE_ENABLED
            and self._credential_file()
            and settings.GOOGLE_DRIVE_FOLDER_ID
        )

    def verify_connection(self) -> dict:
        """
        Test Google Drive connectivity step by step.
        Returns a detailed diagnostic dict with per-step status flags:
            ok                      : bool — overall pass/fail
            credentials_file_exists : bool
            service_account_loaded  : bool
            drive_client_initialized: bool
            folder_accessible       : bool
            message                 : str — human-readable summary
        """
        import os as _os

        result = {
            "ok": False,
            "credentials_file_exists": False,
            "service_account_loaded": False,
            "drive_client_initialized": False,
            "folder_accessible": False,
            "message": "",
        }

        cred_path = self._credential_file()
        folder_id = (
            _os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()
            or settings.GOOGLE_DRIVE_FOLDER_ID
        )

        # Step 1: credential file
        if not cred_path:
            result["message"] = (
                "GOOGLE_SERVICE_ACCOUNT_FILE is not set. "
                "Set it in .env and restart the server."
            )
            return result

        if not _os.path.exists(cred_path):
            result["message"] = (
                f"Service account file not found at: {cred_path}. "
                f"Verify the path is correct and the file exists."
            )
            return result

        result["credentials_file_exists"] = True

        # Step 2: load credentials
        try:
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_file(
                cred_path,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
            result["service_account_loaded"] = True
            logger.info(
                f"Google Drive verify: credentials loaded for "
                f"{credentials.service_account_email}"
            )
        except Exception as exc:
            result["message"] = (
                f"Service account credentials failed to load: {exc}. "
                f"Verify the JSON key file is valid."
            )
            return result

        # Step 3: build Drive API client
        try:
            from googleapiclient.discovery import build
            service = build("drive", "v3", credentials=credentials, cache_discovery=False)
            result["drive_client_initialized"] = True
            logger.info("Google Drive verify: Drive API client initialized.")
        except Exception as exc:
            result["message"] = (
                f"Drive API client failed to initialize: {exc}. "
                f"Verify the Google Drive API is enabled in Cloud Console."
            )
            return result

        # Step 4: folder access
        if not folder_id:
            result["message"] = (
                "Drive API client initialized but GOOGLE_DRIVE_FOLDER_ID is not set. "
                "Add the folder ID to .env."
            )
            return result

        try:
            folder = (
                service.files()
                .get(fileId=folder_id, fields="id, name, mimeType")
                .execute()
            )
            result["folder_accessible"] = True
            result["ok"] = True
            result["message"] = (
                f"Connected successfully. "
                f"Folder: '{folder.get('name', 'unknown')}' (id={folder.get('id')})"
            )
            logger.info(f"Google Drive verify: folder '{folder.get('name')}' accessible.")
        except Exception as exc:
            error_str = str(exc)
            if "404" in error_str or "notFound" in error_str:
                result["message"] = (
                    f"Folder not found (HTTP 404). Folder ID: {folder_id}. "
                    f"The service account '{credentials.service_account_email}' "
                    f"does not have access to this folder. "
                    f"Share the folder with the service account email as Viewer in Google Drive."
                )
            elif "403" in error_str:
                result["message"] = (
                    f"Permission denied (HTTP 403) for folder {folder_id}. "
                    f"The service account has no access. "
                    f"Share the folder with '{credentials.service_account_email}' as Viewer."
                )
            else:
                result["message"] = f"Folder access failed: {exc}"
            logger.error(f"Google Drive verify: {result['message']}")

        return result

    def fetch_documents(self) -> list[MCPDocument]:
        if not self.is_configured():
            logger.info(
                "Google Drive MCP: not configured "
                "(GOOGLE_DRIVE_ENABLED=false or missing credentials/folder). "
                "Skipping."
            )
            return []

        if not os.path.exists(self._credential_file()):
            logger.error(
                f"Google Drive MCP: service account file not found: {self._credential_file()}"
            )
            return []

        try:
            service = self._build_drive_service()
        except Exception as exc:
            logger.error(f"Google Drive MCP: authentication failed: {exc}")
            return []

        try:
            drive_files = self._list_all_files(
                service, settings.GOOGLE_DRIVE_FOLDER_ID
            )
        except Exception as exc:
            logger.error(f"Google Drive MCP: failed to list files: {exc}")
            return []

        logger.info(
            f"Google Drive MCP: found {len(drive_files)} files "
            f"in folder {settings.GOOGLE_DRIVE_FOLDER_ID}"
        )

        # Load already-ingested file IDs from ChromaDB for incremental sync
        already_ingested = self._get_already_ingested_ids()

        documents: list[MCPDocument] = []
        skipped = 0

        for file_meta in drive_files:
            file_id = file_meta["id"]
            filename = file_meta["name"]

            if file_id in already_ingested:
                logger.debug(
                    f"Google Drive MCP: skipping {filename} (already ingested)"
                )
                skipped += 1
                continue

            try:
                t = time.monotonic()
                file_bytes = self._download_file(service, file_id)

                is_docx = filename.lower().endswith(".docx")
                suffix = ".docx" if is_docx else ".pdf"

                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(file_bytes)
                    tmp_path = tmp.name

                try:
                    if is_docx:
                        from app.services.rag_service import extract_text_from_docx
                        text = extract_text_from_docx(tmp_path)
                    else:
                        from app.services.rag_service import extract_text_from_pdf
                        text = extract_text_from_pdf(tmp_path)
                finally:
                    os.unlink(tmp_path)

                if not text.strip():
                    logger.warning(
                        f"Google Drive MCP: no extractable text in {filename} — skipping."
                    )
                    continue

                documents.append(
                    MCPDocument(
                        title=filename,
                        content=text,
                        source=self.source_name,
                        document_type=self._infer_type(filename),
                        metadata={
                            "source": "google_drive",
                            "drive_file_id": file_id,
                            "drive_file_name": filename,
                            "drive_web_view_link": file_meta.get("webViewLink", ""),
                            "folder_id": settings.GOOGLE_DRIVE_FOLDER_ID,
                        },
                    )
                )
                logger.info(
                    f"Google Drive MCP: loaded '{filename}' "
                    f"({len(text)} chars, {time.monotonic()-t:.2f}s)"
                )

            except Exception as exc:
                logger.error(
                    f"Google Drive MCP: failed to process '{filename}': {exc}",
                    exc_info=True,
                )

        self.last_total_found = len(drive_files)
        self.last_skipped_count = skipped

        logger.info(
            f"Google Drive MCP: sync complete — "
            f"{len(documents)} new documents loaded, "
            f"{skipped} skipped (already ingested), "
            f"{len(drive_files) - len(documents) - skipped} failed."
        )
        return documents

    def _build_drive_service(self):
        """Build an authenticated Google Drive API service using a Service Account."""
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = service_account.Credentials.from_service_account_file(
            self._credential_file(),
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        return build("drive", "v3", credentials=credentials, cache_discovery=False)

    def _list_all_files(
        self, service, folder_id: str, visited_folders: Optional[set[str]] = None
    ) -> list[dict]:
        """
        Recursively list all PDF and DOCX files under a given folder ID.
        Handles full pagination via nextPageToken so no files are missed
        in large folders (>100 items). Prevents circular loops by tracking visited folders.
        """
        if visited_folders is None:
            visited_folders = set()

        if folder_id in visited_folders:
            logger.warning(
                f"Google Drive MCP: Circular folder reference detected for folder_id '{folder_id}'. Skipping."
            )
            return []

        visited_folders.add(folder_id)
        drive_files: list[dict] = []

        logger.info(f"Google Drive MCP: Listing files in folder_id '{folder_id}'")

        # Collect all PDF and DOCX files in the given folder
        page_token: Optional[str] = None
        while True:
            query = (
                f"'{folder_id}' in parents "
                f"and (mimeType='application/pdf' or mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document') "
                f"and trashed=false"
            )
            kwargs = {
                "q": query,
                "fields": "nextPageToken, files(id, name, webViewLink)",
                "pageSize": 1000,
            }
            if page_token:
                kwargs["pageToken"] = page_token

            response = service.files().list(**kwargs).execute()
            drive_files.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        # Recursively traverse sub-folders
        subfolder_token: Optional[str] = None
        while True:
            subfolders_query = (
                f"'{folder_id}' in parents "
                f"and mimeType='application/vnd.google-apps.folder' "
                f"and trashed=false"
            )
            kwargs = {
                "q": subfolders_query,
                "fields": "nextPageToken, files(id, name, webViewLink)",
                "pageSize": 1000,
            }
            if subfolder_token:
                kwargs["pageToken"] = subfolder_token

            response = service.files().list(**kwargs).execute()
            subfolders = response.get("files", [])

            for subfolder in subfolders:
                name = subfolder.get("name", "")
                if name.lower() in {'venv', 'node_modules', '.git', '__pycache__', 'dist', 'build', '.vscode', '.idea', 'env'}:
                    logger.warning(
                        f"Google Drive MCP: Ignoring dependency/system folder '{name}'"
                    )
                    continue

                logger.info(
                    f"Google Drive MCP: traversing sub-folder '{name}' (id={subfolder['id']})"
                )
                drive_files.extend(
                    self._list_all_files(service, subfolder["id"], visited_folders=visited_folders)
                )

            subfolder_token = response.get("nextPageToken")
            if not subfolder_token:
                break

        return drive_files

    def _download_file(self, service, file_id: str) -> bytes:
        """Download a file by ID and return raw bytes."""
        from googleapiclient.http import MediaIoBaseDownload

        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()

    def _get_already_ingested_ids(self) -> set[str]:
        """
        Query ChromaDB for all chunks that have a drive_file_id in their metadata
        and return that set of IDs.

        This covers both:
          - Files ingested via MCP sync (source=google_drive)
          - Files uploaded through the UI that were simultaneously pushed to Drive

        Incremental sync uses this set to skip re-downloading files already in
        ChromaDB regardless of which ingestion path added them.
        """
        try:
            from app.services.rag_service import _collection  # noqa: PLC0415

            # Query all chunks that carry a source=google_drive tag.
            # Falls back to scanning all metadatas for drive_file_id if the
            # source field is absent (e.g. data ingested before this change).
            results = _collection.get(
                where={"source": {"$eq": "google_drive"}},
                include=["metadatas"],
            )
            ids: set[str] = set()
            for meta in (results.get("metadatas") or []):
                if meta and meta.get("drive_file_id"):
                    ids.add(meta["drive_file_id"])

            # Also pick up any legacy chunks that have drive_file_id but no
            # source field (written by older versions of the code).
            if not ids:
                all_results = _collection.get(include=["metadatas"])
                for meta in (all_results.get("metadatas") or []):
                    if meta and meta.get("drive_file_id"):
                        ids.add(meta["drive_file_id"])

            logger.debug(
                f"Google Drive MCP: {len(ids)} file IDs already in ChromaDB"
            )
            return ids
        except Exception as exc:
            logger.debug(f"Google Drive MCP: could not load ingested IDs: {exc}")
            return set()

    def _infer_type(self, filename: str) -> str:
        lower = filename.lower()
        if "policy" in lower or "pol" in lower:
            return "policy"
        if "regulation" in lower or "reg" in lower:
            return "regulation"
        return "general"

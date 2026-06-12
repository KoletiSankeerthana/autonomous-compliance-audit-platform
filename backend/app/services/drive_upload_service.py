"""
Google Drive upload service.

Handles the write side of the Google Drive integration:
uploading locally-saved PDF files into the configured Drive folder
immediately after they are saved to disk.

Scopes:
  Read/Sync path  : drive.readonly (GoogleDriveMCPSource)
  Upload path     : drive.file     (DriveUploadService — this module)

drive.file is the narrowest scope that allows creating files.
It only grants access to files this application creates or opens.

Duplicate prevention:
  Before uploading, this service queries the target folder for an existing
  file with the same name. If found, it returns the existing file's metadata
  without creating a duplicate. This makes uploads idempotent.

Configuration (backend/.env):
  GOOGLE_DRIVE_ENABLED=true
  GOOGLE_SERVICE_ACCOUNT_FILE=/absolute/path/service-account.json
  GOOGLE_DRIVE_FOLDER_ID=<folder-id>

Public API:
  drive_upload_service.is_enabled() -> bool
  drive_upload_service.upload_file(local_path, filename, document_type) -> DriveUploadResult
"""

import os
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Narrowest write scope: only files this app creates or opens.
_UPLOAD_SCOPE = "https://www.googleapis.com/auth/drive.file"


@dataclass
class DriveUploadResult:
    """
    Structured result returned by upload_file().

    Attributes:
        file_id:       Google Drive file ID.
        file_name:     Filename as stored in Drive.
        web_view_link: Browser-accessible URL for the file.
        was_duplicate: True if a file with this name already existed in the
                       folder — no new upload was performed.
    """
    file_id: str
    file_name: str
    web_view_link: str
    was_duplicate: bool


class UploadToGoogleDriveError(Exception):
    """Raised when a Drive upload fails for a known, handleable reason."""


class DriveUploadService:
    """
    Uploads locally-saved PDF files to the configured Google Drive folder.

    All configuration is read lazily (at call time) so this class is safe to
    instantiate at module import time even when Drive is disabled.
    """

    # -----------------------------------------------------------------------
    # Configuration helpers
    # -----------------------------------------------------------------------

    def _credential_file(self) -> str:
        """
        Resolve the service account key file path.
        Reads os.environ directly to bypass the lru_cache singleton in settings.
        Falls back to settings values for compatibility.
        """
        return (
            os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
            or os.environ.get("GOOGLE_DRIVE_CREDENTIALS_JSON", "").strip()
            or settings.GOOGLE_SERVICE_ACCOUNT_FILE
            or settings.GOOGLE_DRIVE_CREDENTIALS_JSON
        )

    def _folder_id(self) -> str:
        return (
            os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()
            or settings.GOOGLE_DRIVE_FOLDER_ID
        )

    def _drive_enabled(self) -> bool:
        env_val = os.environ.get("GOOGLE_DRIVE_ENABLED", "").strip().lower()
        if env_val in ("1", "true", "yes"):
            return True
        if env_val in ("0", "false", "no"):
            return False
        return bool(settings.GOOGLE_DRIVE_ENABLED)

    def _load_credentials(self, scopes: list[str]):
        """
        Loads service account credentials, preferring in-memory env variables
        (GOOGLE_CLIENT_EMAIL, GOOGLE_PRIVATE_KEY) and falling back to the service account file.
        """
        import os as _os
        from google.oauth2 import service_account

        client_email = _os.environ.get("GOOGLE_CLIENT_EMAIL", "").strip() or getattr(settings, "GOOGLE_CLIENT_EMAIL", "").strip()
        private_key = _os.environ.get("GOOGLE_PRIVATE_KEY", "").strip() or getattr(settings, "GOOGLE_PRIVATE_KEY", "").strip()
        client_id = _os.environ.get("GOOGLE_CLIENT_ID", "").strip() or getattr(settings, "GOOGLE_CLIENT_ID", "").strip()

        if client_email and private_key:
            # Decode escaped newlines
            private_key = private_key.replace("\\n", "\n")
            info = {
                "type": "service_account",
                "private_key": private_key,
                "client_email": client_email,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            if client_id:
                info["client_id"] = client_id
                
            project_id = _os.environ.get("GOOGLE_PROJECT_ID", "").strip()
            if not project_id and "@" in client_email:
                parts = client_email.split("@")
                if len(parts) > 1:
                    domain = parts[1]
                    if ".iam.gserviceaccount.com" in domain:
                        project_id = domain.replace(".iam.gserviceaccount.com", "")
            if project_id:
                info["project_id"] = project_id

            logger.info(f"Loaded Google credentials in-memory for email: {client_email}")
            return service_account.Credentials.from_service_account_info(info, scopes=scopes)

        # Fallback to file path
        cred_path = self._credential_file()
        if not cred_path:
            raise ValueError("No Google Drive credentials found in settings or environment variables.")
        if not _os.path.exists(cred_path):
            raise FileNotFoundError(f"Service account file not found at path: {cred_path}")

        logger.info(f"Loaded Google credentials from file: {cred_path}")
        return service_account.Credentials.from_service_account_file(
            cred_path,
            scopes=scopes,
        )

    def is_enabled(self) -> bool:
        """
        Return True if all required configuration is present and the credentials
        are available (file exists on disk or present in env).
        """
        import os
        
        # 1. Check enabled
        if not self._drive_enabled():
            return False
            
        # 2. Check folder ID
        if not self._folder_id():
            return False
            
        # 3. Check credentials (file-based OR in-memory variables)
        cred_path = self._credential_file()
        if cred_path and os.path.exists(cred_path):
            return True

        client_email = os.environ.get("GOOGLE_CLIENT_EMAIL", "").strip() or getattr(settings, "GOOGLE_CLIENT_EMAIL", "").strip()
        private_key = os.environ.get("GOOGLE_PRIVATE_KEY", "").strip() or getattr(settings, "GOOGLE_PRIVATE_KEY", "").strip()
        if client_email and private_key:
            return True

        return False

    # -----------------------------------------------------------------------
    # Drive client
    # -----------------------------------------------------------------------

    def _build_service(self, scope: str):
        """Build an authenticated Drive v3 API client for the given scope."""
        try:
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise UploadToGoogleDriveError(
                "google-api-python-client / google-auth not installed. "
                "Run: pip install google-api-python-client google-auth"
            ) from exc

        try:
            credentials = self._load_credentials(scopes=[scope])
        except Exception as exc:
            raise UploadToGoogleDriveError(f"Google Drive authentication failed: {exc}") from exc

        return build("drive", "v3", credentials=credentials, cache_discovery=False)

    # -----------------------------------------------------------------------
    # Duplicate detection
    # -----------------------------------------------------------------------

    def _find_existing_file(self, service, folder_id: str, filename: str) -> Optional[dict]:
        """
        Search the target folder for a file with exactly the given filename.

        Returns the file metadata dict (id, name, webViewLink) if found,
        or None if no matching file exists.

        Uses the drive.file scope so only files created by this app are visible.
        Files uploaded by other accounts in the same folder are not visible
        under drive.file — this is a security property of the scope.
        To check across all files in the folder, use the read-side service
        (drive.readonly). For the dedup use-case this is sufficient because
        we only care about files we previously uploaded.
        """
        try:
            # Escape filename for Drive query syntax
            safe_name = filename.replace("\\", "\\\\").replace("'", "\\'")
            query = (
                f"name = '{safe_name}' "
                f"and '{folder_id}' in parents "
                f"and mimeType = 'application/pdf' "
                f"and trashed = false"
            )
            response = service.files().list(
                q=query,
                fields="files(id, name, webViewLink)",
                pageSize=1,
            ).execute()
            files = response.get("files", [])
            if files:
                logger.info(
                    f"[DriveUpload] Duplicate detected: '{filename}' already exists "
                    f"in folder {folder_id} (id={files[0]['id']})"
                )
                return files[0]
        except Exception as exc:
            # Non-fatal: if the check fails, proceed with upload
            logger.warning(
                f"[DriveUpload] Duplicate check failed for '{filename}': {exc}. "
                f"Proceeding with upload."
            )
        return None

    # -----------------------------------------------------------------------
    # Upload
    # -----------------------------------------------------------------------

    def upload_file(
        self,
        local_path: str,
        filename: str,
        document_type: str,
    ) -> DriveUploadResult:
        """
        Upload a local PDF to the configured Google Drive folder.

        Duplicate prevention:
            If a file with the same name already exists in the target folder
            (uploaded by this app under drive.file scope), no new file is created.
            The existing file's metadata is returned with was_duplicate=True.

        Args:
            local_path:     Absolute or relative path to the local file.
            filename:       Target filename in Google Drive.
            document_type:  Stored as a Drive file property for MCP filtering.

        Returns:
            DriveUploadResult with file_id, file_name, web_view_link, was_duplicate.

        Raises:
            UploadToGoogleDriveError: for all known, handleable failures.
        """
        if not os.path.exists(local_path):
            raise UploadToGoogleDriveError(
                f"Local file not found: {local_path}"
            )

        folder_id = self._folder_id()
        if not folder_id:
            raise UploadToGoogleDriveError("GOOGLE_DRIVE_FOLDER_ID is not configured.")

        file_size = os.path.getsize(local_path)
        logger.info(
            f"[DriveUpload] Starting upload: '{filename}' "
            f"-> folder={folder_id} type={document_type} size={file_size} bytes"
        )

        try:
            from googleapiclient.http import MediaFileUpload
        except ImportError as exc:
            raise UploadToGoogleDriveError(
                "googleapiclient not installed: pip install google-api-python-client"
            ) from exc

        service = self._build_service(_UPLOAD_SCOPE)

        # ---- Duplicate check ----
        existing = self._find_existing_file(service, folder_id, filename)
        if existing:
            return DriveUploadResult(
                file_id=existing.get("id", ""),
                file_name=existing.get("name", filename),
                web_view_link=existing.get("webViewLink", ""),
                was_duplicate=True,
            )

        # ---- Upload ----
        file_metadata = {
            "name": filename,
            "parents": [folder_id],
            "properties": {
                "document_type": document_type,
                "source": "compliance-ai-platform",
            },
            "description": (
                f"Compliance document — type: {document_type}. "
                f"Uploaded by Enterprise Compliance AI Platform."
            ),
        }

        media = MediaFileUpload(
            local_path,
            mimetype="application/pdf",
            resumable=True,
        )

        try:
            created = (
                service.files()
                .create(
                    body=file_metadata,
                    media_body=media,
                    fields="id, name, webViewLink",
                )
                .execute()
            )
        except Exception as exc:
            error_str = str(exc)
            if "storageQuotaExceeded" in error_str or "Service Accounts do not have storage quota" in error_str:
                raise UploadToGoogleDriveError(
                    f"Upload blocked by Google: Service Accounts do not have storage quota in standard 'My Drive' folders. "
                    f"To enable automatic uploads, you must use a folder located in a Google Workspace **Shared Drive** (Team Drive). "
                    f"Raw error: {exc}"
                ) from exc
            if "403" in error_str:
                raise UploadToGoogleDriveError(
                    f"Permission denied uploading to folder '{folder_id}'. "
                    f"The service account needs Editor (not Viewer) access on the folder. "
                    f"Raw error: {exc}"
                ) from exc
            if "404" in error_str or "notFound" in error_str:
                raise UploadToGoogleDriveError(
                    f"Folder not found: '{folder_id}'. "
                    f"Verify GOOGLE_DRIVE_FOLDER_ID and ensure the folder is shared "
                    f"with the service account. Raw error: {exc}"
                ) from exc
            raise UploadToGoogleDriveError(f"Drive upload failed: {exc}") from exc

        file_id = created.get("id", "")
        file_name = created.get("name", filename)
        web_view_link = created.get("webViewLink", "")

        logger.info(
            f"[DriveUpload] '{filename}' uploaded successfully — "
            f"file_id={file_id} link={web_view_link}"
        )

        return DriveUploadResult(
            file_id=file_id,
            file_name=file_name,
            web_view_link=web_view_link,
            was_duplicate=False,
        )


# Module-level singleton. Safe to import at startup — is_enabled() is evaluated
# lazily, so no network calls or auth attempts occur unless Drive is configured.
drive_upload_service = DriveUploadService()

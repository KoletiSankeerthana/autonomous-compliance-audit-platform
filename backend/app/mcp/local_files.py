"""Local filesystem MCP source. No credentials required."""

import os

from app.core.config import settings
from app.core.logging import get_logger
from app.mcp.base import MCPDocument, MCPSource

logger = get_logger(__name__)

_EXTENSION_TYPE_MAP = {
    "_policy": "policy",
    "_regulation": "regulation",
    "_reg": "regulation",
    "_pol": "policy",
}


class LocalFilesMCPSource(MCPSource):
    """
    Reads PDF files from the configured local directory.
    Document type is inferred from filename suffix:
      - Files containing '_policy' -> type='policy'
      - Files containing '_regulation' or '_reg' -> type='regulation'
      - Otherwise -> type='general'
    """

    @property
    def source_name(self) -> str:
        return "local_files"

    def is_configured(self) -> bool:
        return bool(settings.MCP_LOCAL_FILES_DIR)

    def fetch_documents(self) -> list[MCPDocument]:
        if not self.is_configured():
            logger.warning("Local files MCP: MCP_LOCAL_FILES_DIR not configured.")
            return []

        directory = settings.MCP_LOCAL_FILES_DIR
        if not os.path.isdir(directory):
            logger.warning(f"Local files MCP: directory not found: {directory}")
            return []

        from app.services.rag_service import extract_text_from_pdf

        documents: list[MCPDocument] = []
        for filename in os.listdir(directory):
            if not filename.lower().endswith(".pdf"):
                continue

            file_path = os.path.join(directory, filename)
            try:
                text = extract_text_from_pdf(file_path)
                if not text.strip():
                    logger.warning(f"Local files MCP: no text in {filename}, skipping.")
                    continue

                doc_type = self._infer_type(filename)
                documents.append(
                    MCPDocument(
                        title=filename,
                        content=text,
                        source=self.source_name,
                        document_type=doc_type,
                        metadata={"filename": filename, "path": file_path},
                    )
                )
                logger.info(
                    f"Local files MCP: loaded {filename} as type={doc_type}"
                )
            except Exception as exc:
                logger.error(
                    f"Local files MCP: failed to read {filename}: {exc}",
                    exc_info=True,
                )

        logger.info(
            f"Local files MCP: fetched {len(documents)} documents "
            f"from {directory}"
        )
        return documents

    def _infer_type(self, filename: str) -> str:
        lower = filename.lower()
        for suffix, doc_type in _EXTENSION_TYPE_MAP.items():
            if suffix in lower:
                return doc_type
        return "general"

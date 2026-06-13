"""
Notion MCP source.
Fetches pages from a configured Notion database and converts them to text.

Configuration (in .env):
    NOTION_API_TOKEN=<Notion integration token>
    NOTION_DATABASE_ID=<database ID from Notion URL>

Requires: pip install notion-client
"""

from app.core.config import settings
from app.core.logging import get_logger
from app.mcp.base import MCPDocument, MCPSource

logger = get_logger(__name__)


class NotionMCPSource(MCPSource):
    """Fetches compliance documents from a Notion database."""

    @property
    def source_name(self) -> str:
        return "notion"

    def is_configured(self) -> bool:
        return bool(settings.NOTION_API_TOKEN and settings.NOTION_DATABASE_ID)

    def fetch_documents(self) -> list[MCPDocument]:
        if not self.is_configured():
            logger.info(
                "Notion MCP: not configured "
                "(NOTION_API_TOKEN or NOTION_DATABASE_ID missing). Skipping."
            )
            return []

        try:
            from notion_client import Client
        except ImportError:
            logger.warning(
                "Notion MCP: notion-client not installed. "
                "Run: pip install notion-client"
            )
            return []

        try:
            client = Client(auth=settings.NOTION_API_TOKEN)
            
            # Fetch database info to log the title
            db_info = client.databases.retrieve(database_id=settings.NOTION_DATABASE_ID)
            title = "Unknown Database"
            if "title" in db_info:
                title = "".join(part.get("plain_text", "") for part in db_info["title"])
            logger.info(f"[Notion] Database detected: '{title}' (id={settings.NOTION_DATABASE_ID})")

            pages = self._list_pages(client)
            logger.info(f"[Notion] Pages found: {len(pages)} pages in database")
        except Exception as exc:
            logger.error(f"Notion MCP: failed to list pages: {exc}")
            return []

        already_ingested = self._get_already_ingested_info()
        documents: list[MCPDocument] = []
        skipped = 0

        current_page_ids = {page["id"] for page in pages}

        # Remove orphaned vectors (pages deleted from Notion)
        orphans = set(already_ingested.keys()) - current_page_ids
        if orphans:
            logger.info(f"Notion MCP: removing {len(orphans)} orphaned pages from ChromaDB")
            self._delete_notion_pages(orphans)

        for page in pages:
            try:
                page_id = page["id"]
                last_edited_time = page.get("last_edited_time", "")

                if page_id in already_ingested:
                    ingested_time = already_ingested[page_id]
                    # If we have a timestamp and it matches, skip.
                    if ingested_time and ingested_time == last_edited_time:
                        logger.debug(f"Notion MCP: skipping page {page_id} (unchanged)")
                        skipped += 1
                        continue
                    else:
                        # Page was updated or didn't have a timestamp. Remove old chunks.
                        logger.info(f"Notion MCP: updating page {page_id}")
                        self._delete_notion_pages({page_id})

                title = self._extract_title(page)
                text = self._extract_page_text(client, page_id)

                if not text.strip():
                    logger.warning(f"Notion MCP: page '{title}' has no text, skipping.")
                    continue

                documents.append(
                    MCPDocument(
                        title=title,
                        content=text,
                        source=self.source_name,
                        document_type=self._infer_type(title),
                        metadata={
                            "source": self.source_name,
                            "notion_page_id": page_id,
                            "last_edited_time": last_edited_time,
                            "title": title,
                        },
                    )
                )
                logger.info(f"Notion MCP: loaded page '{title}'")
            except Exception as exc:
                logger.error(
                    f"Notion MCP: failed to process page: {exc}", exc_info=True
                )

        self.last_total_found = len(pages)
        self.last_skipped_count = skipped

        logger.info(f"Notion MCP: sync complete — {len(documents)} new pages loaded, {skipped} skipped.")
        return documents

    def _get_already_ingested_info(self) -> dict[str, str]:
        """Query ChromaDB for notion_page_id and last_edited_time to support sync."""
        try:
            from app.services.rag_service import _collection
            results = _collection.get(
                where={"source": {"$eq": "notion"}},
                include=["metadatas"],
            )
            info: dict[str, str] = {}
            for meta in (results.get("metadatas") or []):
                if meta and meta.get("notion_page_id"):
                    page_id = meta["notion_page_id"]
                    # If multiple chunks exist, they should have the same timestamp, but just in case:
                    info[page_id] = meta.get("last_edited_time", "")
            return info
        except Exception as exc:
            logger.debug(f"Notion MCP: could not load ingested IDs: {exc}")
            return {}

    def _delete_notion_pages(self, page_ids: set[str] | list[str]) -> None:
        """Delete all chunks associated with specific notion_page_ids."""
        if not page_ids:
            return
        try:
            from app.services.rag_service import _collection
            # ChromaDB where condition for in-list is $in
            _collection.delete(
                where={"notion_page_id": {"$in": list(page_ids)}}
            )
        except Exception as exc:
            logger.warning(f"Notion MCP: failed to delete old vectors: {exc}")

    def verify_connection(self) -> dict:
        """
        Test Notion connectivity step by step.
        Returns a detailed diagnostic dict with per-step status flags.
        """
        result = {
            "ok": False,
            "api_token_set": False,
            "database_id_set": False,
            "client_initialized": False,
            "database_accessible": False,
            "message": "",
        }

        if not settings.NOTION_API_TOKEN:
            result["message"] = "NOTION_API_TOKEN is not set in environment settings."
            return result
        result["api_token_set"] = True

        if not settings.NOTION_DATABASE_ID:
            result["message"] = "NOTION_DATABASE_ID is not set in environment settings."
            return result
        result["database_id_set"] = True

        try:
            from notion_client import Client
            client = Client(auth=settings.NOTION_API_TOKEN)
            result["client_initialized"] = True
        except ImportError:
            result["message"] = "notion-client library is not installed."
            return result
        except Exception as exc:
            result["message"] = f"Failed to initialize Notion client: {exc}"
            return result

        try:
            db_info = client.databases.retrieve(database_id=settings.NOTION_DATABASE_ID)
            result["database_accessible"] = True
            result["ok"] = True
            
            # Extract title if possible
            title = "Unknown Database"
            if "title" in db_info:
                title = "".join(part.get("plain_text", "") for part in db_info["title"])
                
            result["message"] = f"Connected successfully. Database: '{title}'"
            logger.info(f"Notion MCP verify: database '{title}' accessible.")
        except Exception as exc:
            error_str = str(exc).lower()
            if "404" in error_str or "not_found" in error_str:
                result["message"] = (
                    f"Database not found (HTTP 404). ID: {settings.NOTION_DATABASE_ID}. "
                    "Ensure the integration is connected to this database."
                )
            elif "401" in error_str or "unauthorized" in error_str:
                result["message"] = "Authentication failed. Check your NOTION_API_TOKEN."
            else:
                result["message"] = f"Database access failed: {exc}"
            logger.error(f"Notion MCP verify: {result['message']}")

        return result

    def _list_pages(self, client) -> list[dict]:
        """Query all pages from the configured Notion database."""
        results = []
        cursor = None
        while True:
            kwargs = {
                "database_id": settings.NOTION_DATABASE_ID,
                "page_size": 100,
            }
            if cursor:
                kwargs["start_cursor"] = cursor

            response = client.databases.query(**kwargs)
            results.extend(response.get("results", []))

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

        return results

    def _extract_title(self, page: dict) -> str:
        """Extract the title property from a Notion page."""
        props = page.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                title_parts = prop.get("title", [])
                return "".join(part.get("plain_text", "") for part in title_parts)
        return f"Page {page['id']}"

    def _extract_page_text(self, client, page_id: str) -> str:
        """Recursively extract all text blocks from a Notion page."""
        blocks = []
        cursor = None

        while True:
            kwargs = {"block_id": page_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor

            response = client.blocks.children.list(**kwargs)
            blocks.extend(response.get("results", []))

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

        text_parts: list[str] = []
        for block in blocks:
            block_type = block.get("type", "")
            block_data = block.get(block_type, {})
            rich_text = block_data.get("rich_text", [])
            text = "".join(part.get("plain_text", "") for part in rich_text)
            if text:
                text_parts.append(text)

        return "\n".join(text_parts)

    def _infer_type(self, title: str) -> str:
        lower = title.lower()
        if "policy" in lower:
            return "policy"
        if "regulation" in lower or "regulatory" in lower:
            return "regulation"
        return "general"

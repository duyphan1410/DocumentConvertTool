"""
Core Tool Implementations and Schema Definitions for DocConvert MCP Server.
Provides 6 standardized tools: search_documents, read_document, convert_document,
tag_document, list_backlinks, write_document_content.
"""
from __future__ import annotations
import os
import json
import shutil
import tempfile
from typing import Any, Dict, List, Optional
from src.mcp.security import (
    is_valid_uuid,
    resolve_safe_doc_path,
    sanitize_target_format,
    get_active_workspace_dir,
    is_path_in_workspace,
)
from src.services.metadata_index import MetadataIndex
from src.services.fuzzy_matcher import calculate_similarity
from src.services.conversion_service import convert_content


# ── MCP Tool Schema Manifest (Anthropic MCP Protocol 2024-11-05) ─────────────

MCP_TOOLS_MANIFEST: List[Dict[str, Any]] = [
    {
        "name": "search_documents",
        "description": "Searches Markdown documents in the DocConvert knowledge base by title fuzzy matching and tag filtering.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keyword or phrase to match against document titles (supports Vietnamese accents and fuzzy matching)."
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of tags to filter by (AND condition: document must contain all specified tags)."
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "maximum": 50,
                    "description": "Maximum number of search results to return."
                }
            },
            "required": []
        }
    },
    {
        "name": "read_document",
        "description": "Reads full Markdown content, metadata, and tags of a document identified by its document_id UUID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "Unique UUID of the document in the SQLite index."
                }
            },
            "required": ["document_id"]
        }
    },
    {
        "name": "convert_document",
        "description": "Converts an indexed Markdown document into a target format (docx, pdf, html, json, yaml, csv, txt) and saves it alongside the source file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "Unique UUID of the document to convert."
                },
                "target_format": {
                    "type": "string",
                    "enum": ["docx", "pdf", "html", "json", "yaml", "csv", "txt"],
                    "description": "Desired output format."
                }
            },
            "required": ["document_id", "target_format"]
        }
    },
    {
        "name": "tag_document",
        "description": "Adds or removes tags for an indexed document, updating the SQLite index and tag relations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "Unique UUID of the document."
                },
                "add_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tag names to add."
                },
                "remove_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tag names to remove."
                }
            },
            "required": ["document_id"]
        }
    },
    {
        "name": "list_backlinks",
        "description": "Retrieves bidirectional linked references (incoming wikilinks) and unlinked mentions for a document.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "Unique UUID of the target document."
                }
            },
            "required": ["document_id"]
        }
    },
    {
        "name": "write_document_content",
        "description": "Safely overwrites document content on disk with backup and triggers immediate index synchronization.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "Unique UUID of the document to update."
                },
                "content": {
                    "type": "string",
                    "description": "New Markdown content to write to the file."
                },
                "create_backup": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to create a .bak backup file before overwriting (defaults to true)."
                }
            },
            "required": ["document_id", "content"]
        }
    }
]


# ── Tool Handlers ────────────────────────────────────────────────────────────

def handle_search_documents(
    query: Optional[str] = None,
    tags: Optional[List[str]] = None,
    limit: int = 10,
    index: Optional[MetadataIndex] = None,
    workspace_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Handles document search by title fuzzy matching and tag filtering, scoped to active workspace."""
    idx = index or MetadataIndex.get_instance()
    clean_query = (query or "").strip()
    tag_filters = [t.strip().lstrip("#") for t in (tags or []) if t.strip()]
    limit = max(1, min(limit or 10, 50))
    ws = workspace_dir or get_active_workspace_dir()

    with idx.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, path, title, content_hash, updated_at FROM documents ORDER BY updated_at DESC")
        rows = cursor.fetchall()

    results = []
    for row in rows:
        doc_id = row["id"]
        doc_path = row["path"]
        
        # Only return files that physically exist on disk
        if not doc_path or not os.path.exists(doc_path) or not os.path.isfile(doc_path):
            continue

        # Enforce active workspace boundary containment
        if ws and not is_path_in_workspace(doc_path, ws):
            continue

        title = row["title"] or os.path.basename(doc_path)
        doc_tags = idx.get_document_tags(doc_id)

        # 1. Tag Filtering (AND condition)
        if tag_filters:
            doc_tag_set = {t.lower() for t in doc_tags}
            if not all(tf.lower() in doc_tag_set for tf in tag_filters):
                continue

        # 2. Query Fuzzy & Substring Scoring
        score = 1.0
        if clean_query:
            filename = os.path.basename(doc_path)
            stem = os.path.splitext(filename)[0]
            
            title_score = calculate_similarity(clean_query, title)
            stem_score = calculate_similarity(clean_query, stem)
            score = max(title_score, stem_score)

            # Substring bonus
            cq_lower = clean_query.lower()
            if cq_lower in title.lower() or cq_lower in filename.lower() or cq_lower.replace("_", " ") in title.lower():
                score = max(score, 0.85)

            # Skip if relevance is too low
            if score < 0.35:
                continue

        results.append({
            "document_id": doc_id,
            "title": title,
            "path": doc_path,
            "tags": doc_tags,
            "updated_at": row["updated_at"],
            "relevance_score": round(score, 3)
        })

    # Sort results by relevance score descending, then title ascending
    results.sort(key=lambda item: (-item["relevance_score"], item["title"].lower()))
    clipped_results = results[:limit]

    return {
        "query": clean_query,
        "tags_filter": tag_filters,
        "total_matches": len(results),
        "results": clipped_results
    }


def handle_read_document(
    document_id: str,
    index: Optional[MetadataIndex] = None,
    workspace_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Reads document content from disk safely using its document_id."""
    idx = index or MetadataIndex.get_instance()
    is_valid, safe_path, doc = resolve_safe_doc_path(document_id, idx, workspace_dir=workspace_dir)

    if not is_valid or not safe_path:
        return {
            "error": "DOCUMENT_NOT_FOUND",
            "message": f"Document ID '{document_id}' not found in index, file does not exist, or outside workspace boundary.",
            "document_id": document_id
        }

    try:
        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        tags = idx.get_document_tags(document_id)

        return {
            "document_id": document_id,
            "title": doc.get("title", os.path.basename(safe_path)) if doc else os.path.basename(safe_path),
            "path": safe_path,
            "tags": tags,
            "updated_at": doc.get("updated_at") if doc else None,
            "content": content
        }
    except Exception as e:
        return {
            "error": "READ_ERROR",
            "message": f"Failed to read file: {str(e)}",
            "document_id": document_id
        }


def handle_convert_document(
    document_id: str,
    target_format: str,
    index: Optional[MetadataIndex] = None,
    workspace_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Converts indexed Markdown document to target format and saves alongside source file."""
    idx = index or MetadataIndex.get_instance()
    is_valid, safe_path, doc = resolve_safe_doc_path(document_id, idx, workspace_dir=workspace_dir)

    if not is_valid or not safe_path:
        return {
            "error": "DOCUMENT_NOT_FOUND",
            "message": f"Document ID '{document_id}' not found in index, file does not exist, or outside workspace boundary.",
            "document_id": document_id
        }

    try:
        clean_fmt = sanitize_target_format(target_format)
    except ValueError as ve:
        return {
            "error": "INVALID_FORMAT",
            "message": str(ve),
            "document_id": document_id
        }

    try:
        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Build output path in same directory as source file
        base_dir = os.path.dirname(safe_path)
        stem = os.path.splitext(os.path.basename(safe_path))[0]
        out_path = os.path.join(base_dir, f"{stem}.{clean_fmt}")

        # Map to ConversionService mode: MD -> TARGET
        dest_upper = clean_fmt.upper()
        if dest_upper == "TXT":
            with open(out_path, "w", encoding="utf-8") as out_f:
                out_f.write(content)
            result_msg = f"Saved to Plain Text -> {os.path.basename(out_path)}"
        else:
            mode = f"MD -> {dest_upper}"
            result_msg = convert_content(mode, content, out_path)

        return {
            "document_id": document_id,
            "source_path": safe_path,
            "target_format": clean_fmt,
            "output_path": out_path,
            "result_message": result_msg,
            "status": "success"
        }
    except Exception as e:
        return {
            "error": "CONVERSION_ERROR",
            "message": f"Conversion failed: {str(e)}",
            "document_id": document_id,
            "target_format": target_format
        }


def handle_tag_document(
    document_id: str,
    add_tags: Optional[List[str]] = None,
    remove_tags: Optional[List[str]] = None,
    index: Optional[MetadataIndex] = None,
    workspace_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Updates document tags by calculating diff and updating SQLite index."""
    idx = index or MetadataIndex.get_instance()
    is_valid, safe_path, doc = resolve_safe_doc_path(document_id, idx, workspace_dir=workspace_dir)

    if not is_valid:
        return {
            "error": "DOCUMENT_NOT_FOUND",
            "message": f"Document ID '{document_id}' not found in index or outside workspace boundary.",
            "document_id": document_id
        }

    current_tags = idx.get_document_tags(document_id)
    current_set = set(current_tags)

    to_add = {t.strip().lstrip("#") for t in (add_tags or []) if t.strip()}
    to_remove = {t.strip().lstrip("#").lower() for t in (remove_tags or []) if t.strip()}

    # Calculate new tag set
    new_set = {t for t in current_set if t.lower() not in to_remove}
    new_set.update(to_add)
    final_tags = sorted(list(new_set))

    idx.set_document_tags(document_id, final_tags)

    return {
        "document_id": document_id,
        "previous_tags": current_tags,
        "current_tags": final_tags,
        "added": sorted(list(to_add)),
        "removed": sorted(list(to_remove)),
        "status": "success"
    }


def handle_list_backlinks(
    document_id: str,
    index: Optional[MetadataIndex] = None,
    workspace_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieves linked references and unlinked mentions for a document within active workspace."""
    idx = index or MetadataIndex.get_instance()
    is_valid, safe_path, doc = resolve_safe_doc_path(document_id, idx, workspace_dir=workspace_dir)

    if not is_valid or not doc:
        return {
            "error": "DOCUMENT_NOT_FOUND",
            "message": f"Document ID '{document_id}' not found in index or outside workspace boundary.",
            "document_id": document_id
        }

    ws = workspace_dir or get_active_workspace_dir()

    linked_refs = []
    with idx.get_connection() as conn:
        cursor = conn.cursor()
        # Find all documents referencing target_id
        cursor.execute("""
            SELECT w.source_id, d.title AS source_title, d.path AS source_path, w.snippet, w.display_text
            FROM wikilinks w
            JOIN documents d ON w.source_id = d.id
            WHERE w.target_id = ?
            ORDER BY d.title ASC
        """, (document_id,))
        for r in cursor.fetchall():
            source_path = r["source_path"]
            if ws and not is_path_in_workspace(source_path, ws):
                continue
            linked_refs.append({
                "source_id": r["source_id"],
                "source_title": r["source_title"],
                "source_path": source_path,
                "snippet": r["snippet"],
                "display_text": r["display_text"]
            })

    target_title = doc.get("title", "")
    unlinked_mentions = []
    if target_title and safe_path:
        try:
            search_ws = ws or os.path.dirname(safe_path)
            raw_unlinked = idx.find_unlinked_mentions_in_workspace(target_title, safe_path, search_ws)
            for item in raw_unlinked:
                item_path = item.get("source_path")
                if ws and item_path and not is_path_in_workspace(item_path, ws):
                    continue
                unlinked_mentions.append({
                    "source_path": item_path,
                    "source_title": item.get("source_title"),
                    "snippet": item.get("snippet"),
                    "matched_text": item.get("matched_text")
                })
        except Exception:
            pass

    return {
        "document_id": document_id,
        "title": target_title,
        "linked_references_count": len(linked_refs),
        "linked_references": linked_refs,
        "unlinked_mentions_count": len(unlinked_mentions),
        "unlinked_mentions": unlinked_mentions
    }


def handle_write_document_content(
    document_id: str,
    content: str,
    index: Optional[MetadataIndex] = None,
    workspace_dir: Optional[str] = None,
    create_backup: bool = True
) -> Dict[str, Any]:
    """
    Safely overwrites document content with single .bak backup and atomic file write,
    then triggers immediate SQLite re-indexing.
    """
    idx = index or MetadataIndex.get_instance()
    is_valid, safe_path, doc = resolve_safe_doc_path(document_id, idx, workspace_dir=workspace_dir)

    if not is_valid or not safe_path:
        return {
            "error": "DOCUMENT_NOT_FOUND",
            "message": f"Document ID '{document_id}' not found in index, file does not exist, or outside workspace boundary.",
            "document_id": document_id
        }

    try:
        # 1. Create a single backup .bak before overwrite
        if create_backup and os.path.exists(safe_path):
            backup_path = f"{safe_path}.bak"
            shutil.copy2(safe_path, backup_path)

        # 2. Atomic Write via NamedTemporaryFile in the same directory
        dir_name = os.path.dirname(safe_path)
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            tf.write(content)
            temp_name = tf.name

        os.replace(temp_name, safe_path)

        # 3. Trigger immediate re-index to update hash, tags, and links in SQLite
        idx.index_document(safe_path)

        return {
            "document_id": document_id,
            "path": safe_path,
            "bytes_written": len(content.encode("utf-8")),
            "backup_created": create_backup,
            "status": "success",
            "message": "File written atomically and indexed successfully."
        }
    except Exception as e:
        return {
            "error": "WRITE_ERROR",
            "message": f"Failed to write file content: {str(e)}",
            "document_id": document_id
        }


# ── Tool Dispatcher Map ──────────────────────────────────────────────────────

TOOL_HANDLERS = {
    "search_documents": handle_search_documents,
    "read_document": handle_read_document,
    "convert_document": handle_convert_document,
    "tag_document": handle_tag_document,
    "list_backlinks": handle_list_backlinks,
    "write_document_content": handle_write_document_content
}

"""
Core Tool Implementations and Schema Definitions for DocConvert MCP Server.
Provides 11 standardized tools: search_documents, read_document, convert_document,
tag_document, list_backlinks, write_document_content, patch_document_content,
get_document_history, rollback_document, cleanup_legacy_backups,
import_document_to_markdown.
"""
from __future__ import annotations
import os
import re
import json
import uuid
import shutil
import zipfile
import logging
import tempfile
from typing import Any, Dict, List, Optional
from src.mcp.security import (
    is_valid_uuid,
    is_strictly_within,
    resolve_safe_doc_path,
    resolve_doc_for_restore,
    sanitize_target_format,
    get_active_workspace_dir,
    is_path_in_workspace,
)
from src.utils.file_ops import safe_delete_to_recycle_bin
from src.services.metadata_index import MetadataIndex
from src.services.fuzzy_matcher import calculate_similarity
from src.services.conversion_service import convert_content
from src.services.file_loader import load_document, LoadResult
from src.services.media_asset_manager import MediaAssetManager


logger = logging.getLogger("docconvert.mcp.tools")


# Registry lookup key uses module.name (display label), which differs
# from the uppercase format string for these 3 modules.
_FORMAT_TO_MODULE_NAME = {"DOCX": "Word", "PPTX": "PowerPoint", "XLSX": "Excel"}


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
        "description": "Converts an indexed Markdown document into a target format (docx, pptx, xlsx, pdf, html, json, yaml, csv, txt) and saves it alongside the source file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "Unique UUID of the document to convert."
                },
                "target_format": {
                    "type": "string",
                    "enum": ["docx", "pptx", "xlsx", "pdf", "html", "json", "yaml", "csv", "txt"],
                    "description": "Desired output format (docx, pptx, xlsx, pdf, html, json, yaml, csv, txt)."
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
        "description": "Safely overwrites document content on disk atomically, captures version history snapshot, and triggers index synchronization.",
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
                "change_summary": {
                    "type": "string",
                    "description": "Optional short description of changes made for the version history log."
                },
                "create_backup": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to create a legacy .bak backup file before overwriting (defaults to false; SQLite version history is the primary store)."
                }
            },
            "required": ["document_id", "content"]
        }
    },
    {
        "name": "patch_document_content",
        "description": "Safely patches a specific unique text block in a Markdown document. Prevents accidental document truncation and enforces strict single-match verification.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "Unique UUID v4 of the document to patch."
                },
                "target_content": {
                    "type": "string",
                    "description": "The exact existing text block to be replaced. Must match exactly one occurrence in the document."
                },
                "replacement_content": {
                    "type": "string",
                    "description": "The new replacement text content."
                },
                "change_summary": {
                    "type": "string",
                    "description": "Optional short explanation of what this patch changes for the history log."
                }
            },
            "required": ["document_id", "target_content", "replacement_content"]
        }
    },
    {
        "name": "get_document_history",
        "description": "Retrieves version timeline, authors, timestamps, and change summaries for a document. Does not return full body text to conserve token context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "Unique UUID v4 of the document."
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "maximum": 50,
                    "description": "Maximum number of history revisions to retrieve."
                }
            },
            "required": ["document_id"]
        }
    },
    {
        "name": "rollback_document",
        "description": "Restores a document to a previous historical version (default: version 0 baseline). Supports recreating deleted files if history exists.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "Unique UUID v4 of the document."
                },
                "target_version": {
                    "type": "integer",
                    "default": 0,
                    "description": "Target version number to restore (defaults to 0 for initial human baseline)."
                }
            },
            "required": ["document_id"]
        }
    },
    {
        "name": "cleanup_legacy_backups",
        "description": "Scans and cleans up legacy *.bak backup files in the workspace. Requires dry_run=false AND confirm=true to execute deletion. Workspace is automatically resolved server-side.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dry_run": {
                    "type": "boolean",
                    "default": True,
                    "description": "If true (default), only lists found .bak files without deleting them."
                },
                "confirm": {
                    "type": "boolean",
                    "default": False,
                    "description": "Explicit safety confirmation flag. Must be set to true when dry_run=false."
                }
            },
            "required": []
        }
    },
    {
        "name": "import_document_to_markdown",
        "description": "Imports a raw document (docx, pdf, xlsx, csv, html) located inside workspace into a structured Markdown document and indexes it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "Relative or absolute path of the source file within active workspace boundary."
                },
                "output_filename": {
                    "type": "string",
                    "description": "Optional output markdown filename (e.g. 'summary.md'). If omitted, uses source basename with .md extension."
                }
            },
            "required": ["source_path"]
        }
    }
]



# ── Tool Handlers ────────────────────────────────────────────────────────────

def handle_search_documents(
    query: Optional[str] = None,
    tags: Optional[List[str]] = None,
    limit: int = 10,
    index: Optional[MetadataIndex] = None
) -> Dict[str, Any]:
    """Handles document search by title fuzzy matching and tag filtering, scoped to active workspace."""
    idx = index or MetadataIndex.get_instance()
    clean_query = (query or "").strip()
    tag_filters = [t.strip().lstrip("#") for t in (tags or []) if t.strip()]
    limit = max(1, min(limit or 10, 50))
    ws = get_active_workspace_dir()

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
            "path": _rel(doc_path),
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
    index: Optional[MetadataIndex] = None
) -> Dict[str, Any]:
    """Reads document content from disk safely using its document_id."""
    idx = index or MetadataIndex.get_instance()
    is_valid, safe_path, doc = resolve_safe_doc_path(document_id, idx)

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
            "path": _rel(safe_path),
            "tags": tags,
            "updated_at": doc.get("updated_at") if doc else None,
            "content": content
        }
    except Exception as e:
        return {
            "error": "READ_ERROR",
            "message": f"Failed to read file: {_sanitize_error_message(e)}",
            "document_id": document_id
        }


def handle_convert_document(
    document_id: str,
    target_format: str,
    index: Optional[MetadataIndex] = None
) -> Dict[str, Any]:
    """Converts indexed Markdown document to target format and saves alongside source file."""
    idx = index or MetadataIndex.get_instance()
    is_valid, safe_path, doc = resolve_safe_doc_path(document_id, idx)

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
            registry_name = _FORMAT_TO_MODULE_NAME.get(dest_upper, dest_upper)
            mode = f"MD -> {registry_name}"
            result_msg = convert_content(mode, content, out_path)

        return {
            "document_id": document_id,
            "source_path": _rel(safe_path),
            "target_format": clean_fmt,
            "output_path": _rel(out_path),
            "result_message": result_msg,
            "status": "success"
        }
    except Exception as e:
        return {
            "error": "CONVERSION_ERROR",
            "message": f"Conversion failed: {_sanitize_error_message(e)}",
            "document_id": document_id,
            "target_format": target_format
        }


def handle_tag_document(
    document_id: str,
    add_tags: Optional[List[str]] = None,
    remove_tags: Optional[List[str]] = None,
    index: Optional[MetadataIndex] = None
) -> Dict[str, Any]:
    """Updates document tags by calculating diff and updating SQLite index."""
    idx = index or MetadataIndex.get_instance()
    is_valid, safe_path, doc = resolve_safe_doc_path(document_id, idx)

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
    index: Optional[MetadataIndex] = None
) -> Dict[str, Any]:
    """Retrieves linked references and unlinked mentions for a document within active workspace."""
    idx = index or MetadataIndex.get_instance()
    is_valid, safe_path, doc = resolve_safe_doc_path(document_id, idx)

    if not is_valid or not doc:
        return {
            "error": "DOCUMENT_NOT_FOUND",
            "message": f"Document ID '{document_id}' not found in index or outside workspace boundary.",
            "document_id": document_id
        }

    ws = get_active_workspace_dir()

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
                "source_path": _rel(source_path), 
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
                    "source_path": _rel(item_path) if item_path else None,
                    "source_title": item.get("source_title"),
                    "snippet": item.get("snippet"),
                    "matched_text": item.get("matched_text")
                })
        except Exception as ex:
            logger.warning("Unlinked mentions scan failed for %s: %s", document_id, ex)

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
    change_summary: Optional[str] = None,
    create_backup: bool = False,
    index: Optional[MetadataIndex] = None
) -> Dict[str, Any]:
    """
    Safely overwrites document content with atomic file write, captures
    version history snapshot, and triggers SQLite re-indexing.
    """
    idx = index or MetadataIndex.get_instance()
    if not is_valid_uuid(document_id):
        return {
            "error": "INVALID_UUID",
            "message": f"Document ID '{document_id}' is not a valid UUID v4.",
            "document_id": document_id
        }

    is_valid, safe_path, doc = resolve_safe_doc_path(document_id, idx)
    if not is_valid or not safe_path:
        return {
            "error": "DOCUMENT_NOT_FOUND",
            "message": f"Document ID '{document_id}' not found in index, file does not exist, or outside workspace boundary.",
            "document_id": document_id
        }
    temp_name = None 
    try:
        if len(content.encode("utf-8")) > 5 * 1024 * 1024:     
            return {"error": "CONTENT_TOO_LARGE", "message": "Content exceeds 5MB limit.", "document_id": document_id}

        # 1. Capture v0 baseline before mutating file (safe & idempotent)
        if not idx.ensure_baseline_version(document_id):
            return {"error": "BASELINE_FAILED", "message": "Cannot snapshot original version; write aborted.", "document_id": document_id}

        # 2. Optional legacy .bak backup
        if create_backup and os.path.exists(safe_path):
            backup_path = f"{safe_path}.bak"
            shutil.copy2(safe_path, backup_path)

        # 3. Atomic Write via NamedTemporaryFile in the same directory
        dir_name = os.path.dirname(safe_path)
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            tf.write(content)
            temp_name = tf.name

        os.replace(temp_name, safe_path)

        # 4. Append new version snapshot in history (only after disk write succeeds)
        warning_msg: Optional[str] = None
        ver_num: Optional[int] = None
        try:
            ver_num = idx.append_document_version(
                document_id=document_id,
                content=content,
                change_summary=change_summary or "Full document rewrite",
                author="AI"
            )
        except Exception as ex:
            warning_msg = f"File written to disk successfully, but history snapshot failed: {_sanitize_error_message(ex)}"
            logger.warning("History snapshot failed for %s: %s", document_id, ex)

        # 5. Trigger immediate re-index to update hash, tags, and links in SQLite (EC-2)
        try:
            idx.index_document(safe_path)
        except Exception as ex:
            logger.warning("Post-write re-indexing failed for %s: %s", safe_path, ex)

        return {
            "document_id": document_id,
            "path": _rel(safe_path),
            "bytes_written": len(content.encode("utf-8")),
            "version": ver_num,
            "warning": warning_msg,
            "backup_created": create_backup,
            "status": "success",
            "message": "File written atomically and indexed successfully."
        }
    except Exception as e:
        if temp_name and os.path.exists(temp_name):      
            try:
                os.remove(temp_name)
            except OSError:
                pass
        return {
            "error": "WRITE_ERROR",
            "message": f"Failed to write file content: {_sanitize_error_message(e)}",
            "document_id": document_id
        }


def handle_patch_document_content(
    document_id: str,
    target_content: str,
    replacement_content: str,
    change_summary: Optional[str] = None,
    index: Optional[MetadataIndex] = None
) -> Dict[str, Any]:
    """
    Safely patches a specific unique text block in a Markdown document.
    Enforces strict single-match verification to eliminate silent wrong replace.
    """
    idx = index or MetadataIndex.get_instance()
    if not is_valid_uuid(document_id):
        return {
            "error": "INVALID_UUID",
            "message": f"Document ID '{document_id}' is not a valid UUID v4.",
            "document_id": document_id
        }

    is_valid, safe_path, doc = resolve_safe_doc_path(document_id, idx)
    if not is_valid or not safe_path:
        return {
            "error": "DOCUMENT_NOT_FOUND",
            "message": f"Document ID '{document_id}' not found in index, file does not exist, or outside workspace boundary.",
            "document_id": document_id
        }
    temp_name = None
    try:
        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            current_content = f.read()

        match_count = current_content.count(target_content)
        if match_count == 0:
            return {
                "error": "TARGET_NOT_FOUND",
                "message": "target_content was not found in document. Please call read_document to verify current content.",
                "document_id": document_id
            }
        elif match_count > 1:
            return {
                "error": "MULTIPLE_MATCHES_FOUND",
                "message": f"target_content matched {match_count} occurrences. Please provide a longer unique surrounding block to match exactly once.",
                "match_count": match_count,
                "document_id": document_id
            }

        patched_content = current_content.replace(target_content, replacement_content, 1)

        # 1. Capture v0 baseline before mutating file
        if not idx.ensure_baseline_version(document_id):
            return {"error": "BASELINE_FAILED", "message": "Cannot snapshot original version; write aborted.", "document_id": document_id}

        # 2. Atomic disk write
        dir_name = os.path.dirname(safe_path)
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            tf.write(patched_content)
            temp_name = tf.name

        os.replace(temp_name, safe_path)

        # 3. Append history snapshot
        warning_msg: Optional[str] = None
        ver_num: Optional[int] = None
        try:
            ver_num = idx.append_document_version(
                document_id=document_id,
                content=patched_content,
                change_summary=change_summary or "Applied text patch",
                author="AI"
            )
        except Exception as ex:
            warning_msg = f"Patch applied to disk successfully, but history snapshot failed: {_sanitize_error_message(ex)}"
            logger.warning("History snapshot failed for %s: %s", document_id, ex)

        # 4. Re-index
        try:
            idx.index_document(safe_path)
        except Exception as ex:
            logger.warning("Post-patch re-indexing failed for %s: %s", safe_path, ex)

        return {
            "document_id": document_id,
            "path": _rel(safe_path),
            "bytes_written": len(patched_content.encode("utf-8")),
            "version": ver_num,
            "warning": warning_msg,
            "status": "success",
            "message": "File patched atomically and indexed successfully."
        }
    except Exception as e:
        if temp_name and os.path.exists(temp_name):     
            try:
                os.remove(temp_name)
            except OSError:
                pass
        return {
            "error": "PATCH_ERROR",
            "message": f"Failed to patch file content: {_sanitize_error_message(e)}",
            "document_id": document_id
        }


def handle_get_document_history(
    document_id: str,
    limit: int = 20,
    index: Optional[MetadataIndex] = None
) -> Dict[str, Any]:
    """
    Retrieves version timeline metadata and change summaries for a document.
    Does not load heavy full content bodies to conserve token bandwidth.
    """
    idx = index or MetadataIndex.get_instance()
    if not is_valid_uuid(document_id):
        return {
            "error": "INVALID_UUID",
            "message": f"Document ID '{document_id}' is not a valid UUID v4.",
            "document_id": document_id
        }

    is_valid, safe_path, doc = resolve_safe_doc_path(document_id, idx)
    if not is_valid or not safe_path:
        return {
            "error": "DOCUMENT_NOT_FOUND",
            "message": f"Document ID '{document_id}' not found in index, file does not exist, or outside workspace boundary.",
            "document_id": document_id
        }

    limit = max(1, min(limit or 20, 50))
    total = idx.count_document_versions(document_id)
    versions = idx.get_document_versions(document_id, limit=limit)

    return {
        "document_id": document_id,
        "total_versions": total,
        "returned_versions": len(versions),
        "versions": versions
    }


def handle_rollback_document(
    document_id: str,
    target_version: int = 0,
    index: Optional[MetadataIndex] = None
) -> Dict[str, Any]:
    """
    Restores a document to a previous historical version (defaults to version 0 baseline).
    Supports recreating physical files if accidentally deleted.
    """
    idx = index or MetadataIndex.get_instance()
    if not is_valid_uuid(document_id):
        return {
            "error": "INVALID_UUID",
            "message": f"Document ID '{document_id}' is not a valid UUID v4.",
            "document_id": document_id
        }

    is_valid, safe_path, doc = resolve_doc_for_restore(document_id, idx)
    if doc is None:
        return {
            "error": "DOCUMENT_NOT_FOUND",
            "message": f"Document ID '{document_id}' not found in index.",
            "document_id": document_id
        }

    if not is_valid or not safe_path:
        return {
            "error": "RESTORE_OUTSIDE_WORKSPACE",
            "message": f"Document path is outside active workspace boundary.",
            "document_id": document_id
        }

    target_content = idx.get_version_content(document_id, target_version)
    if target_content is None:
        return {
            "error": "VERSION_NOT_FOUND",
            "message": f"Version {target_version} not found in history for document '{document_id}'.",
            "document_id": document_id,
            "target_version": target_version
        }

    temp_name = None

    try:
        # Recreate directory structure if needed (e.g. restoring deleted file)
        dir_name = os.path.dirname(safe_path)
        os.makedirs(dir_name, exist_ok=True)

        # Atomic write
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            tf.write(target_content)
            temp_name = tf.name

        os.replace(temp_name, safe_path)

        # Append audit log entry
        warning_msg: Optional[str] = None
        new_ver: Optional[int] = None
        try:
            new_ver = idx.append_document_version(
                document_id=document_id,
                content=target_content,
                change_summary=f"Rollback to version {target_version}",
                author="SYSTEM"
            )
        except Exception as ex:
            warning_msg = f"Rollback content written to disk, but audit logging failed: {_sanitize_error_message(ex)}"
            logger.warning("Audit logging failed during rollback for %s: %s", document_id, ex)

        # Re-index
        try:
            idx.index_document(safe_path)
        except Exception as ex:
            logger.warning("Post-rollback re-indexing failed for %s: %s", safe_path, ex)

        return {
            "document_id": document_id,
            "path": _rel(safe_path),
            "restored_version": target_version,
            "new_version": new_ver,
            "warning": warning_msg,
            "status": "success",
            "message": f"Document restored to version {target_version} successfully."
        }
    except Exception as e:
        if temp_name and os.path.exists(temp_name):
            try:
                os.remove(temp_name)
            except OSError:
                pass
        return {
            "error": "ROLLBACK_ERROR",
            "message": f"Failed to rollback document: {_sanitize_error_message(e)}",
            "document_id": document_id
        }


def handle_cleanup_legacy_backups(
    dry_run: bool = True,
    confirm: bool = False,
    index: Optional[MetadataIndex] = None
) -> Dict[str, Any]:
    """
    Scans and safely cleans up legacy *.bak backup files in the active workspace.
    Requires dry_run=False AND confirm=True to execute safe recycling.
    """
    ws = get_active_workspace_dir()
    if not ws or not os.path.isdir(ws):
        return {
            "error": "WORKSPACE_NOT_FOUND",
            "message": "No active workspace folder is configured or available."
        }

    # Anti-symlink safe traversal
    candidate_files: List[Dict[str, Any]] = []
    total_bytes = 0

    for root, dirs, files in os.walk(ws, followlinks=False):
        for fname in files:
            if fname.endswith(".bak"):
                full_p = os.path.normpath(os.path.join(root, fname))
                if os.path.islink(full_p):
                    continue
                real_p = os.path.realpath(full_p)
                if not is_path_in_workspace(real_p, ws):
                    continue
                try:
                    f_size = os.path.getsize(real_p)
                except OSError:
                    f_size = 0
                candidate_files.append({
                    "path": real_p,
                    "filename": fname,
                    "bytes": f_size
                })
                total_bytes += f_size

    if dry_run:
        return {
            "status": "preview",
            "dry_run": True,
            "workspace": os.path.basename(ws),
            "files_found_count": len(candidate_files),
            "total_bytes": total_bytes,
            "files": [{"path": _rel(i["path"]), "filename": i["filename"], "bytes": i["bytes"]} for i in candidate_files],
            "message": "Dry run preview: no files were deleted. Pass dry_run=false AND confirm=true to execute deletion."
        }

    if not confirm:
        return {
            "error": "CONFIRMATION_REQUIRED",
            "message": "Cleanup is a destructive action. You must explicitly pass confirm=true alongside dry_run=false.",
            "files_found_count": len(candidate_files),
            "total_bytes": total_bytes
        }

    deleted_count = 0
    failed_files = []
    for item in candidate_files:
        f_path = item["path"]
        try:
            safe_delete_to_recycle_bin(f_path)
            deleted_count += 1
        except Exception as ex:
            failed_files.append({"path": _rel(f_path), "error": _sanitize_error_message(ex)})

    if failed_files and deleted_count == 0:
        return {
            "error": "CLEANUP_FAILED",
            "message": f"Failed to recycle backup files safely: {failed_files[0]['error']}",
            "failed_files": failed_files
        }

    return {
        "status": "success",
        "dry_run": False,
        "workspace": os.path.basename(ws),
        "deleted_count": deleted_count,
        "total_bytes_reclaimed": total_bytes,
        "failed_files": failed_files,
        "message": f"Successfully moved {deleted_count} backup files to recycle bin."
    }


# ── Import Raw Document Helpers & Handler ────────────────────────────────────

WINDOWS_RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
})


def _sanitize_filename_stem(raw_name: Optional[str], fallback_stem: str) -> str:
    """Sanitizes filename stem, blocking Windows device names (including NUL.tar.gz), ADS colons, and illegal characters."""
    if not raw_name:
        return fallback_stem
    base = os.path.basename(raw_name)
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', base).strip('. ')
    if not clean or clean.startswith('.'):
        return fallback_stem
    first_part = clean.split('.')[0].strip().upper()
    if first_part in WINDOWS_RESERVED_NAMES:
        return fallback_stem
    stem = os.path.splitext(clean)[0].strip('. ')
    if not stem or stem.upper() in WINDOWS_RESERVED_NAMES:
        return fallback_stem
    return stem[:100]


def _sanitize_error_message(err: Exception | str) -> str:
    """Sanitizes error messages, removing Windows absolute drive paths and UNC network paths."""
    raw = str(err)
    clean = re.sub(r'[a-zA-Z]:[/\\][^:\n\r]+', '<path>', raw)
    clean = re.sub(r'(?<!\w)/(?:[\w.\-]+/)+[\w.\-]*', '<path>', clean)
    clean = re.sub(r'\\\\[^:\n\r]+', '<path>', clean)
    return clean[:300]

def _rel(p: str) -> str:
    ws = get_active_workspace_dir()
    try:
        return os.path.relpath(p, ws).replace("\\", "/") if ws else os.path.basename(p)
    except ValueError:
        return os.path.basename(p)

def _check_office_zip_safety(file_path: str, max_uncompressed_bytes: int = 50 * 1024 * 1024, max_entries: int = 2000) -> Optional[str]:
    """Inspects docx/xlsx zip container safety. Returns error code if unsafe or corrupt."""
    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            infolist = z.infolist()
            if len(infolist) > max_entries:
                return "ZIP_BOMB_DETECTED"
            total_size = sum(info.file_size for info in infolist)
            if total_size > max_uncompressed_bytes:
                return "ZIP_BOMB_DETECTED"
            compressed_size = sum(info.compress_size for info in infolist)

            ratio = (total_size / compressed_size) if compressed_size > 0 else 0
            logger.debug("Office zip safety check for %s: ratio=%.2f (compressed=%d, uncompressed=%d)", 
                         os.path.basename(file_path), ratio, compressed_size, total_size)
                         
            if compressed_size > 0 and (total_size / compressed_size) > 100:
                return "ZIP_BOMB_DETECTED"
            return None
    except PermissionError as pe:
        logger.warning("Permission denied checking office zip: %s", pe)
        raise pe
    except zipfile.BadZipFile:
        return "CORRUPTED_ARCHIVE"
    except Exception:
        return "CORRUPTED_ARCHIVE"


def handle_import_document_to_markdown(
    source_path: str,
    output_filename: Optional[str] = None,
    index: Optional[MetadataIndex] = None
) -> Dict[str, Any]:
    """Imports raw document (docx, pdf, xlsx, csv, html) into indexed Markdown document."""
    idx = index or MetadataIndex.get_instance()

    ws_dir = get_active_workspace_dir()
    
    if not ws_dir or not os.path.isdir(ws_dir):
        logger.warning("import_document_to_markdown: WORKSPACE_NOT_INITIALIZED")
        return {
            "error": "WORKSPACE_NOT_INITIALIZED",
            "message": "No active workspace folder is configured."
        }

    raw_path = source_path if os.path.isabs(source_path) else os.path.join(ws_dir, source_path)
    real_src_path = os.path.realpath(raw_path)

    logger.info("Executing tool 'import_document_to_markdown' for file: %s", os.path.basename(real_src_path))

    if not is_strictly_within(real_src_path, ws_dir):
        return {
            "error": "PATH_OUTSIDE_WORKSPACE",
            "message": "Source path is outside workspace boundary."
        }

    if not os.path.isfile(real_src_path):
        return {
            "error": "FILE_NOT_FOUND",
            "message": "Source file not found on disk."
        }

    ext = os.path.splitext(real_src_path)[1].lower()
    ALLOWED_EXTENSIONS = {".docx", ".pdf", ".xlsx", ".csv", ".html"}
    if ext not in ALLOWED_EXTENSIONS:
        return {
            "error": "UNSUPPORTED_FORMAT",
            "message": f"Extension '{ext}' is not supported in Phase 1 (allowed: {sorted(list(ALLOWED_EXTENSIONS))})."
        }

    MAX_INPUT_SIZE = 10 * 1024 * 1024
    if os.path.getsize(real_src_path) > MAX_INPUT_SIZE:
        return {
            "error": "FILE_TOO_LARGE_FOR_SYNC",
            "message": "File exceeds 10MB limit for synchronous import."
        }

    if ext in {".docx", ".xlsx"}:
        try:
            zip_err = _check_office_zip_safety(real_src_path)
        except PermissionError:
            logger.warning("import_document_to_markdown: ACCESS_DENIED — %s", os.path.basename(real_src_path))
            return {"error": "ACCESS_DENIED", "message": "Cannot read source file (locked or no permission)."}
        if zip_err == "ZIP_BOMB_DETECTED":
            return {
                "error": "ZIP_BOMB_DETECTED",
                "message": "Uncompressed content exceeds safety limits."
            }
        elif zip_err == "CORRUPTED_ARCHIVE":
            return {
                "error": "IMPORT_FAILED",
                "message": "Corrupted or invalid Office zip package."
            }

    if ext == ".pdf":
        try:
            import fitz
            with fitz.open(real_src_path) as pdf_doc:
                # Only reject when a user password is required (needs_pass).
                # owner_pw-only PDFs are readable and should not be blocked.
                if getattr(pdf_doc, "needs_pass", False):
                    logger.warning("import_document_to_markdown: ENCRYPTED_DOCUMENT — %s", os.path.basename(real_src_path))
                    return {
                        "error": "ENCRYPTED_DOCUMENT",
                        "message": "PDF is password-protected (user password required)."
                    }
                if len(pdf_doc) == 0:
                    logger.warning("import_document_to_markdown: EMPTY_DOCUMENT — %s", os.path.basename(real_src_path))
                    return {
                        "error": "EMPTY_DOCUMENT",
                        "message": "PDF has 0 pages."
                    }
                if len(pdf_doc) > 30:
                    logger.warning("import_document_to_markdown: PDF_PAGE_LIMIT_EXCEEDED (%d pages) — %s", len(pdf_doc), os.path.basename(real_src_path))
                    return {
                        "error": "PDF_PAGE_LIMIT_EXCEEDED",
                        "message": f"PDF has {len(pdf_doc)} pages (max 30 for sync import)."
                    }
        except ImportError:
            return {
                "error": "MISSING_DEPENDENCIES",
                "message": "PyMuPDF (fitz) is not installed."
            }
        except Exception as ex:
            logger.warning("import_document_to_markdown: IMPORT_FAILED (PDF open) — %s", os.path.basename(real_src_path))
            return {
                "error": "IMPORT_FAILED",
                "message": f"Invalid PDF structure: {_sanitize_error_message(ex)}"
            }

    session_id = f"mcp_import_{uuid.uuid4().hex[:12]}"
    asset_mgr = MediaAssetManager()

    reservation_token = None
    target_md_path = None
    temp_write_path = None
    doc_id = None

    assets_dir = None
    assets_pre_existed = True
    import_ok = False

    try:
        load_res: LoadResult = load_document(real_src_path, session_id=session_id)

        if load_res.missing_dependencies:
            return {
                "error": "MISSING_DEPENDENCIES",
                "message": f"Missing required dependencies: {', '.join(load_res.missing_dependencies)}"
            }

        if not load_res.success:
            return {
                "error": "IMPORT_FAILED",
                "message": _sanitize_error_message(load_res.error_detail or load_res.error_short or "Extraction failed.")
            }

        # For PDF: use strict clean-text threshold (image-only scans produce < 10 chars).
        # For other formats (docx/xlsx/csv/html): reject only when content is completely empty.
        if ext == ".pdf":
            clean_text = re.sub(r'!\[.*?\]\(.*?\)|<img.*?>|\*\(Empty PDF\)\*|[#\s\-_*`>=|:]', '', load_res.content or '')
            if len(clean_text) < 10:
                logger.warning("import_document_to_markdown: EMPTY_CONTENT (scanned PDF) — %s", os.path.basename(real_src_path))
                return {
                    "error": "EMPTY_CONTENT",
                    "message": "Document contains no extractable text (e.g. image-only scanned PDF). OCR engine is required."
                }
        else:
            if not (load_res.content or "").strip():
                logger.warning("import_document_to_markdown: EMPTY_CONTENT — %s", os.path.basename(real_src_path))
                return {
                    "error": "EMPTY_CONTENT",
                    "message": "Document contains no extractable text."
                }

        MAX_OUTPUT_BYTES = 5 * 1024 * 1024
        content_bytes = load_res.content.encode("utf-8")
        if len(content_bytes) > MAX_OUTPUT_BYTES:
            logger.warning("import_document_to_markdown: OUTPUT_TOO_LARGE (%d chars) — %s", len(content_bytes), os.path.basename(real_src_path))
            return {
                "error": "OUTPUT_TOO_LARGE",
                "message": "Extracted Markdown content exceeds 5MB limit. Consider splitting the document."
            }

        src_stem = os.path.splitext(os.path.basename(real_src_path))[0]
        safe_stem = _sanitize_filename_stem(output_filename, fallback_stem=src_stem)
        target_dir = os.path.dirname(real_src_path)

        counter = 0
        while True:
            if counter > 1000:
                raise RuntimeError("Too many files with the same name in the workspace.")
            cand_stem = safe_stem if counter == 0 else f"{safe_stem}_{counter}"
            cand_md = os.path.join(target_dir, f"{cand_stem}.md")
            cand_res = os.path.join(target_dir, f".{cand_stem}.md.reserve")
            try:
                if not os.path.exists(cand_md):
                    fd = os.open(cand_res, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.close(fd)
                    reservation_token = cand_res
                    target_md_path = cand_md
                    break
            except FileExistsError:
                pass
            counter += 1
        assets_dir = os.path.join(target_dir, f"{os.path.splitext(os.path.basename(target_md_path))[0]}_assets")
        assets_pre_existed = os.path.exists(assets_dir)

        final_markdown = asset_mgr.export_assets(
            load_res.content,
            target_md_path,
            session_id=session_id,
            session_only=True
        )

        with tempfile.NamedTemporaryFile("w", dir=target_dir, suffix=".tmp", delete=False, encoding="utf-8") as tf:
            tf.write(final_markdown)
            temp_write_path = tf.name

        try:
            os.rename(temp_write_path, target_md_path)
            temp_write_path = None
        except FileExistsError:
            return {
                "error": "TARGET_FILE_CONFLICT",
                "message": "Target file was created concurrently. Please retry."
            }

        doc_id = idx.index_document(target_md_path)
        if not doc_id:
            raise RuntimeError("MetadataIndex failed to index the generated Markdown file.")

        warning_msg: Optional[str] = None
        try:
            if not idx.ensure_baseline_version(doc_id):
                warning_msg = "Version snapshot warning: baseline not created."
        except Exception as ex:
            warning_msg = f"Version snapshot warning: {_sanitize_error_message(ex)}"
            logger.warning("Version baseline creation failed for %s: %s", doc_id, ex)

        import_ok = True

        res_dict = {
            "status": "success",
            "document_id": doc_id,
            "relative_path": os.path.relpath(target_md_path, os.path.realpath(ws_dir)).replace("\\", "/"),
            "message": f"Successfully imported '{os.path.basename(real_src_path)}' to Markdown."
        }
        if warning_msg:
            res_dict["warning"] = warning_msg
        return res_dict

    except Exception as exc:
        if target_md_path and os.path.exists(target_md_path) and not doc_id:
            try:
                os.remove(target_md_path)
            except Exception:
                pass
        return {
            "error": "IMPORT_FAILED",
            "message": _sanitize_error_message(exc)
        }

    finally:
        if not import_ok and assets_dir and not assets_pre_existed and os.path.isdir(assets_dir):
            shutil.rmtree(assets_dir, ignore_errors=True)
        if reservation_token and os.path.exists(reservation_token):
            try:
                os.remove(reservation_token)
            except Exception:
                pass
        if temp_write_path and os.path.exists(temp_write_path):
            try:
                os.remove(temp_write_path)
            except Exception:
                pass
        asset_mgr.clear_session(session_id)


# ── Tool Dispatcher Map ──────────────────────────────────────────────────────

TOOL_HANDLERS = {
    "search_documents": handle_search_documents,
    "read_document": handle_read_document,
    "convert_document": handle_convert_document,
    "tag_document": handle_tag_document,
    "list_backlinks": handle_list_backlinks,
    "write_document_content": handle_write_document_content,
    "patch_document_content": handle_patch_document_content,
    "get_document_history": handle_get_document_history,
    "rollback_document": handle_rollback_document,
    "cleanup_legacy_backups": handle_cleanup_legacy_backups,
    "import_document_to_markdown": handle_import_document_to_markdown,
}


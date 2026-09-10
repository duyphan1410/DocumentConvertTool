"""
Security Guard and Path Traversal Prevention for DocConvert Local MCP Server.
Ensures zero-leakage, ID-only surface validation, and strict file boundary resolution.
"""
from __future__ import annotations
import os
import uuid
from typing import Optional, Tuple, Any

# Supported target formats for MD -> Target programmatic conversion
SUPPORTED_CONVERT_FORMATS = frozenset([
    "docx", "pdf", "html", "json", "yaml", "csv", "txt"
])


def is_valid_uuid(val: Any) -> bool:
    """Validates if a given string or value conforms to standard UUID format."""
    if not val or not isinstance(val, str):
        return False
    try:
        uuid.UUID(str(val).strip())
        return True
    except (ValueError, AttributeError):
        return False


def resolve_safe_doc_path(doc_id: str, index: Any) -> Tuple[bool, Optional[str], Optional[dict]]:
    """
    Prevents path traversal by enforcing ID-only lookups strictly against the SQLite index.
    
    Returns:
        (is_valid_and_exists, absolute_file_path, document_record_dict)
    """
    if not is_valid_uuid(doc_id):
        return False, None, None

    doc = index.get_document_by_id(doc_id)
    if not doc:
        return False, None, None

    stored_path = doc.get("path")
    if not stored_path or not isinstance(stored_path, str):
        return False, None, doc

    # Normalize path and check file existence on physical disk
    norm_path = os.path.normpath(os.path.abspath(stored_path))
    if not os.path.exists(norm_path) or not os.path.isfile(norm_path):
        return False, None, doc

    return True, norm_path, doc


def sanitize_target_format(target_format: str) -> str:
    """
    Validates and normalizes target export format.
    Raises ValueError if format is unsupported.
    """
    if not target_format or not isinstance(target_format, str):
        raise ValueError("Target format must be a non-empty string.")
    
    clean_fmt = target_format.strip().lower().lstrip(".")
    if clean_fmt not in SUPPORTED_CONVERT_FORMATS:
        valid_list = ", ".join(sorted(SUPPORTED_CONVERT_FORMATS))
        raise ValueError(f"Unsupported target format: '{target_format}'. Supported formats: {valid_list}")
    
    return clean_fmt

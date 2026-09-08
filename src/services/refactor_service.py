"""
Refactor Rename Service for PKB Graph Integrity (v1.10.0).
Safely cascades document renames across all markdown files in workspace,
updating wikilinks [[Old Title]], [[Old Title|Alias]], [[Old Title#Heading]],
transclusions ![[Old Title]], and relative markdown links to prevent broken references.
"""
from __future__ import annotations

import os
import re
from typing import Optional, List, Tuple, Dict, Any


def refactor_markdown_links(
    content: str,
    old_target: str,
    new_target: str,
    old_path: Optional[str] = None,
    new_path: Optional[str] = None,
) -> Tuple[str, int]:
    """
    Replaces occurrences of old_target with new_target inside wikilinks and transclusions.
    Preserves aliases and section headings:
    - [[Old Title]] -> [[New Title]]
    - [[Old Title|Alias]] -> [[New Title|Alias]]
    - [[Old Title#Section]] -> [[New Title#Section]]
    - ![[Old Title]] -> ![[New Title]]
    - ![[Old Title#Section]] -> ![[New Title#Section]]
    - ![[Old Title|Option]] -> ![[New Title|Option]]

    Returns:
        (updated_content, replacement_count)
    """
    if not content or not old_target or not new_target:
        return content, 0

    if old_target == new_target:
        return content, 0

    # Identify excluded ranges (fenced code blocks, inline code)
    excluded_ranges: list[tuple[int, int]] = []
    for m in re.finditer(r'(?m)^[ \t]*```[^\r\n]*\r?\n[\s\S]*?(?:^[ \t]*```|\Z)', content):
        excluded_ranges.append((m.start(), m.end()))
    for m in re.finditer(r'`+[^`\r\n]+`+', content):
        excluded_ranges.append((m.start(), m.end()))

    def _is_excluded(start: int, end: int) -> bool:
        for ex_s, ex_e in excluded_ranges:
            if not (end <= ex_s or start >= ex_e):
                return True
        return False

    old_clean = old_target.strip()
    new_clean = new_target.strip()
    old_escaped = re.escape(old_clean)

    # Pattern matches:
    # 1. [[old_target]]
    # 2. [[old_target|alias]]
    # 3. [[old_target#heading]]
    # 4. [[old_target#heading|alias]]
    # 5. Same with leading ! for transclusions
    pattern = re.compile(rf'(!?)\[\[({old_escaped})((?:#[^\]\|]+)?)(?:\|([^\]]+))?\]\]', re.IGNORECASE)

    count = 0
    result = list(content)

    for m in reversed(list(pattern.finditer(content))):
        if _is_excluded(m.start(), m.end()):
            continue
        
        is_embed = m.group(1) or ""
        heading_part = m.group(3) or ""
        alias_part = m.group(4)

        if alias_part:
            replacement = f"{is_embed}[[{new_clean}{heading_part}|{alias_part}]]"
        else:
            replacement = f"{is_embed}[[{new_clean}{heading_part}]]"

        result[m.start():m.end()] = list(replacement)
        count += 1

    # Also check standard relative markdown links if old_path and new_path are given
    updated_str = "".join(result)
    if old_path and new_path:
        old_base = os.path.basename(old_path)
        new_base = os.path.basename(new_path)
        if old_base != new_base:
            md_link_pat = re.compile(rf'(?<!!)\[([^\]]+)\]\(([^)]*{re.escape(old_base)}[^)]*)\)')
            for m in reversed(list(md_link_pat.finditer(updated_str))):
                if _is_excluded(m.start(), m.end()):
                    continue
                display = m.group(1)
                link_url = m.group(2).replace(old_base, new_base)
                rep = f"[{display}]({link_url})"
                updated_str = updated_str[:m.start()] + rep + updated_str[m.end():]
                count += 1

    return updated_str, count


def refactor_document_rename_workspace(
    old_path: str,
    new_path: str,
    workspace_folder: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Cascades a document rename across all markdown files in the workspace.
    Updates all referencing wikilinks and relative links.
    Atomically saves modified files to disk and triggers index updates.

    Returns:
        {
            "files_scanned": int,
            "files_modified": int,
            "links_updated": int,
            "modified_file_paths": List[str]
        }
    """
    old_norm = os.path.normpath(os.path.abspath(old_path))
    new_norm = os.path.normpath(os.path.abspath(new_path))

    old_stem = os.path.splitext(os.path.basename(old_path))[0]
    new_stem = os.path.splitext(os.path.basename(new_path))[0]
    old_basename = os.path.basename(old_path)
    new_basename = os.path.basename(new_path)

    search_dir = workspace_folder
    if not search_dir or not os.path.exists(search_dir):
        search_dir = os.path.dirname(old_norm)

    files_scanned = 0
    files_modified = 0
    links_updated = 0
    modified_paths = []

    # Gather all markdown files in workspace
    md_files = []
    for root, _, files in os.walk(search_dir):
        for f in files:
            if f.lower().endswith((".md", ".markdown")):
                full_p = os.path.normpath(os.path.abspath(os.path.join(root, f)))
                md_files.append(full_p)

    for fpath in md_files:
        files_scanned += 1
        # Skip old path if it somehow lingers in file list
        if fpath == old_norm:
            continue

        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            # 1. Refactor by Title / Stem
            updated_content, cnt1 = refactor_markdown_links(
                content, old_stem, new_stem, old_path=old_norm, new_path=new_norm
            )

            # 2. Refactor by Full Basename (for non-md or exact filename links)
            if old_basename != old_stem:
                updated_content, cnt2 = refactor_markdown_links(
                    updated_content, old_basename, new_basename
                )
                cnt1 += cnt2

            if cnt1 > 0:
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(updated_content)
                files_modified += 1
                links_updated += cnt1
                modified_paths.append(fpath)
        except Exception as ex:
            print(f"[RefactorService] Error processing file {fpath}: {ex}")

    # Synchronize MetadataIndex
    try:
        from src.services.metadata_index import MetadataIndex
        idx = MetadataIndex.get_instance()
        idx.rename_document(old_norm, new_norm, new_stem)
        if search_dir and os.path.exists(search_dir):
            idx.sync_workspace_incremental(search_dir)
    except Exception as ex:
        print(f"[RefactorService] MetadataIndex sync error: {ex}")

    return {
        "files_scanned": files_scanned,
        "files_modified": files_modified,
        "links_updated": links_updated,
        "modified_file_paths": modified_paths,
    }

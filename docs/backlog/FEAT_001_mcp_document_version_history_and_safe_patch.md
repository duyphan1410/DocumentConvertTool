# FEAT_001: MCP Document Version History, Safe Patch & Rollback Engine

**Status**: PROPOSED  
**Date**: 2026-09-14  
**Tags**: `mcp`, `sqlite`, `version-history`, `safety`, `diff-patch`

---

## 1. Executive Summary & Problem Statement

Currently, the `docconvert/write_document_content` MCP tool allows AI agents to overwrite Markdown documents directly. Although an atomic temporary file write and single `.bak` file are generated, this design introduces critical vulnerabilities when AI agents perform multi-step modifications:
1. **Cascading Overwrite Data Loss**: If an AI makes multiple successive edits ($N, N+1$), the initial user baseline ($N-1$) is permanently overwritten by the intermediate state ($N$).
2. **Full File Truncation & Hallucination**: Overwriting the whole document requires the AI to send the entire content. For large files, AI models frequently truncate sections or drop footnotes/tables inadvertently.
3. **No Rollback to Original Baseline**: The user cannot easily "Revert to human-authored baseline" or inspect a timeline of changes made across AI sessions.

---

## 2. Proposed Architecture & Multi-Layer Defense

```
[AI Agent / MCP Client]
          │
          ├── 1. Partial Edit Mode (Patch / Search & Replace)
          │      └── AI only modifies targeted lines; 95%+ of unchanged document is untouched.
          │
          ├── 2. Baseline & Version History Engine (SQLite)
          │      ├── Version 0: Auto-captures human original baseline before first AI write.
          │      ├── Version N: Incremental revisions with author ('AI'/'USER'), timestamp & summary.
          │      └── Pruning/Retention: Max revisions per document or manual cleanup.
          │
          └── 3. Safe Rollback & Diff Inspection Tools
                 ├── `get_document_history`: Lists all revisions with diff summaries.
                 └── `rollback_document`: Restores document to any revision (e.g., Version 0) atomically.
```

---

## 3. Database Schema Design (`index.db`)

Add a new table `document_history` to `src/services/metadata_index.py`:

```sql
CREATE TABLE IF NOT EXISTS document_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,          -- 0 for original baseline, 1, 2, ... for subsequent revisions
    content TEXT NOT NULL,             -- Full snapshot of markdown content at this revision
    change_summary TEXT,               -- Descriptive summary (e.g., "Initial baseline before AI edits", "Updated table format")
    author TEXT NOT NULL DEFAULT 'AI', -- 'USER' or 'AI'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_history_doc_ver ON document_history(document_id, version);
```

---

## 4. MCP Tool Additions & Modifications

### 4.1 Update `write_document_content`
- **Auto Baseline Capture**: Before writing, if no revision exists in `document_history`, snapshot the current on-disk content as `version = 0` (`author = 'USER'`).
- **Append Revision**: Save the new content as `version = MAX(version) + 1` (`author = 'AI'`).
- **Atomic Disk Write**: Maintain existing `NamedTemporaryFile` + `os.replace` behavior.
- **Deprecate Disk `.bak`**: Set `create_backup = False` by default to prevent workspace clutter, relying on SQLite `document_history` as the primary versioning store.

### 4.2 New Tool: `patch_document_content`
- Accepts `document_id`, `target_content`, `replacement_content`, and optional `change_summary`.
- Replaces exact substring/block, reducing token usage and eliminating silent document truncation.

### 4.3 New Tool: `get_document_history`
- Accepts `document_id`.
- Returns metadata list: `[{version, author, created_at, change_summary, bytes_count}]`.

### 4.4 New Tool: `rollback_document`
- Accepts `document_id` and `target_version` (defaults to `0` for original baseline).
- Restores disk file and SQLite index to the specified historical snapshot.

### 4.5 New Tool: `cleanup_legacy_backups`
- Safely scans and removes residual `.bak` files across the active workspace.
- Supports dry-run preview and moves legacy backup files safely via `safe_delete_to_recycle_bin`.

---

## 5. Implementation Roadmap

| Phase | Milestone | Deliverables |
|:---|:---|:---|
| **Phase 1** | Schema & Index Extension | Add `document_history` table and CRUD methods in `MetadataIndex`. |
| **Phase 2** | MCP Tools Hardening | Implement `patch_document_content`, `rollback_document`, `cleanup_legacy_backups`, and update `write_document_content`. |
| **Phase 3** | Integration & Unit Tests | Automated test suite covering multiple overwrites, baseline rollback, patch failure safeguards, and backup cleanup. |
| **Phase 4** | UI Integration (Optional) | Add "History / Restore" drawer/modal and "Clean Backups" button in DocConvert Flet UI. |


"""
SQLite Metadata Index Service for Personal Knowledge Base (PKB Phase 1).
Manages documents, tags, wikilinks, incremental 3-way sync, and thread-safe operations.
Path: %APPDATA%/DocConvert/index.db
"""
from __future__ import annotations
import os
import re
import sqlite3
import hashlib
import threading
import uuid
from typing import Optional, Callable, Any
from contextlib import contextmanager
from src.services.link_parser import WikilinkToken, extract_wikilinks, extract_tags, find_unlinked_mentions

# SQLite DB Path in AppData / Custom Env
_appdata = os.getenv("APPDATA", os.path.expanduser("~"))
DEFAULT_DB_DIR = os.path.join(_appdata, "DocConvert")
_env_db_path = os.getenv("DOCCONVERT_INDEX_PATH")
if _env_db_path:
    DEFAULT_DB_PATH = os.path.abspath(os.path.expandvars(os.path.expanduser(_env_db_path)))
else:
    DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "index.db")


class MetadataIndex:
    _instance: Optional[MetadataIndex] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls, db_path: Optional[str] = None) -> MetadataIndex:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db_path=db_path or DEFAULT_DB_PATH)
            return cls._instance

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = os.path.abspath(os.path.expandvars(os.path.expanduser(db_path)))
        self._write_lock = threading.RLock()
        self._init_db()

    def _create_tables(self, conn: sqlite3.Connection):
        """Creates tables and indexes on the connection if they don't exist."""
        cursor = conn.cursor()
        # 1. Documents Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL UNIQUE COLLATE NOCASE,
                title TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_path ON documents(path COLLATE NOCASE);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_title ON documents(title);")

        # 2. Tags Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                normalized_name TEXT NOT NULL UNIQUE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_normalized ON tags(normalized_name);")

        # 3. Document Tags Junction Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_tags (
                document_id TEXT NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (document_id, tag_id),
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            );
        """)

        # 4. Wikilinks Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wikilinks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT,
                target_title_raw TEXT NOT NULL,
                display_text TEXT,
                snippet TEXT,
                resolved INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES documents(id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES documents(id) ON DELETE SET NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wikilinks_source ON wikilinks(source_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wikilinks_target ON wikilinks(target_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wikilinks_raw ON wikilinks(target_title_raw);")
        conn.commit()

    @contextmanager
    def get_connection(self):
        """Yields a thread-safe connection configured with WAL mode and busy timeout."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(
            self.db_path,
            timeout=10.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("PRAGMA foreign_keys=ON;")
            # Self-healing: verify schema existence in case db was deleted or recreated externally
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='documents'")
            if not cur.fetchone():
                with self._write_lock:
                    self._create_tables(conn)
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Initializes database schema and indexes."""
        with self._write_lock:
            with self.get_connection() as conn:
                self._create_tables(conn)

    @staticmethod
    def calculate_hash(content: str) -> str:
        """Computes SHA-256 hash of text content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    # ── Document CRUD ──────────────────────────────────────────────────────────

    def upsert_document(self, path: str, title: str, content_hash: str, doc_id: Optional[str] = None) -> str:
        """Inserts or updates a document metadata record, preserving its UUID."""
        norm_path = os.path.normpath(os.path.abspath(path))
        with self._write_lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM documents WHERE path = ? COLLATE NOCASE", (norm_path,))
                row = cursor.fetchone()
                if row:
                    existing_id = row["id"]
                    cursor.execute("""
                        UPDATE documents 
                        SET title = ?, content_hash = ?, updated_at = CURRENT_TIMESTAMP 
                        WHERE id = ?
                    """, (title, content_hash, existing_id))
                    conn.commit()
                    return existing_id
                else:
                    new_id = doc_id or str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO documents (id, path, title, content_hash)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(path) DO UPDATE SET
                            title = excluded.title,
                            content_hash = excluded.content_hash,
                            updated_at = CURRENT_TIMESTAMP
                    """, (new_id, norm_path, title, content_hash))
                    conn.commit()
                    cursor.execute("SELECT id FROM documents WHERE path = ? COLLATE NOCASE", (norm_path,))
                    r = cursor.fetchone()
                    return r["id"] if r else new_id

    def index_document(self, file_path: str) -> Optional[str]:
        """Indexes or updates a single markdown file on disk, parsing tags and wikilinks."""
        from src.services.fuzzy_matcher import normalize_vietnamese
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return None

        norm_path = os.path.normpath(os.path.abspath(file_path))
        try:
            with open(norm_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            return None

        new_hash = self.calculate_hash(content)

        # Extract Title
        title = os.path.splitext(os.path.basename(norm_path))[0]
        first_heading_m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if first_heading_m:
            raw_h1 = first_heading_m.group(1).strip()
            clean_h1 = re.sub(r'[*_`]', '', raw_h1)
            clean_h1 = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean_h1).strip()
            if clean_h1:
                title = clean_h1

        with self._write_lock:
            with self.get_connection() as conn:
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM documents WHERE path = ?", (norm_path,))
                    row = cursor.fetchone()
                    if row:
                        doc_id = row["id"]
                        cursor.execute("""
                            UPDATE documents 
                            SET title = ?, content_hash = ?, updated_at = CURRENT_TIMESTAMP 
                            WHERE id = ?
                        """, (title, new_hash, doc_id))
                    else:
                        doc_id = str(uuid.uuid4())
                        cursor.execute("""
                            INSERT INTO documents (id, path, title, content_hash)
                            VALUES (?, ?, ?, ?)
                        """, (doc_id, norm_path, title, new_hash))

                    # Sync Tags
                    tags = extract_tags(content)
                    cursor.execute("DELETE FROM document_tags WHERE document_id = ?", (doc_id,))
                    for tag in tags:
                        clean_tag = tag.strip().lstrip("#")
                        if not clean_tag:
                            continue
                        norm_tag = normalize_vietnamese(clean_tag).replace(" ", "-")
                        cursor.execute("""
                            INSERT INTO tags (name, normalized_name)
                            VALUES (?, ?)
                            ON CONFLICT(name) DO UPDATE SET normalized_name = excluded.normalized_name
                        """, (clean_tag, norm_tag))
                        cursor.execute("SELECT id FROM tags WHERE name = ?", (clean_tag,))
                        tag_row = cursor.fetchone()
                        if tag_row:
                            cursor.execute("""
                                INSERT OR IGNORE INTO document_tags (document_id, tag_id)
                                VALUES (?, ?)
                            """, (doc_id, tag_row["id"]))

                    # Sync Wikilinks
                    wikilinks = extract_wikilinks(content)
                    cursor.execute("DELETE FROM wikilinks WHERE source_id = ?", (doc_id,))
                    for wl in wikilinks:
                        clean_target = wl.raw_target.strip()
                        cursor.execute("""
                            SELECT id FROM documents 
                            WHERE title = ? OR path LIKE ? OR path LIKE ?
                        """, (clean_target, f"%{os.sep}{clean_target}.md", f"%/{clean_target}.md"))
                        t_row = cursor.fetchone()
                        if not t_row:
                            cursor.execute("SELECT id FROM documents WHERE LOWER(title) = LOWER(?)", (clean_target,))
                            t_row = cursor.fetchone()

                        target_id = t_row["id"] if t_row else None
                        resolved = 1 if target_id else 0

                        cursor.execute("""
                            INSERT INTO wikilinks (
                                source_id, target_id, target_title_raw, display_text, snippet, resolved
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        """, (doc_id, target_id, wl.raw_target, wl.display_text, wl.snippet, resolved))

                    return doc_id

    def get_document_by_id(self, doc_id: str, include_tags: bool = True) -> Optional[dict]:
        """Retrieves document record by UUID, optionally including its tags list."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            row = cursor.fetchone()
            if not row:
                return None
            doc_dict = dict(row)
            if include_tags:
                doc_dict["tags"] = self.get_document_tags(doc_id)
            return doc_dict

    def get_document_tags(self, doc_id: str) -> list[str]:
        """Retrieves list of tag names associated with a document_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.name 
                FROM tags t 
                JOIN document_tags dt ON t.id = dt.tag_id 
                WHERE dt.document_id = ?
                ORDER BY t.name ASC
            """, (doc_id,))
            return [row[0] for row in cursor.fetchall()]

    def get_document_by_path(self, path: str) -> Optional[dict]:
        """Retrieves document record by absolute path."""
        norm_path = os.path.normpath(os.path.abspath(path))
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE path = ?", (norm_path,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def rename_document(self, old_path: str, new_path: str, new_title: str) -> bool:
        """
        Atomically updates document path and title via UPDATE.
        Preserves the document UUID, preventing cascading deletion of incoming wikilinks.
        """
        old_norm = os.path.normpath(os.path.abspath(old_path))
        new_norm = os.path.normpath(os.path.abspath(new_path))
        with self._write_lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE documents 
                    SET path = ?, title = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE path = ?
                """, (new_norm, new_title, old_norm))
                conn.commit()
                return cursor.rowcount > 0

    def delete_document(self, doc_id: str) -> bool:
        """Deletes a document record and cascades removal of document_tags and source wikilinks."""
        with self._write_lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                conn.commit()
                return cursor.rowcount > 0

    # ── Tag Management ─────────────────────────────────────────────────────────

    def set_document_tags(self, doc_id: str, tag_names: list[str]) -> None:
        """Synchronizes document tags in SQLite."""
        from src.services.fuzzy_matcher import normalize_vietnamese
        with self._write_lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Clear existing tags for this document
                cursor.execute("DELETE FROM document_tags WHERE document_id = ?", (doc_id,))

                for tag in tag_names:
                    clean_tag = tag.strip().lstrip("#")
                    if not clean_tag:
                        continue
                    norm_tag = normalize_vietnamese(clean_tag).replace(" ", "-")

                    # Upsert tag in tags table
                    cursor.execute("""
                        INSERT INTO tags (name, normalized_name)
                        VALUES (?, ?)
                        ON CONFLICT(name) DO UPDATE SET normalized_name = excluded.normalized_name
                    """, (clean_tag, norm_tag))

                    cursor.execute("SELECT id FROM tags WHERE name = ?", (clean_tag,))
                    tag_row = cursor.fetchone()
                    if tag_row:
                        tag_id = tag_row["id"]
                        cursor.execute("""
                            INSERT OR IGNORE INTO document_tags (document_id, tag_id)
                            VALUES (?, ?)
                        """, (doc_id, tag_id))

                # Purge orphan tags that are no longer referenced by any document
                cursor.execute("DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM document_tags)")
                conn.commit()

    def get_all_tags(self, only_active: bool = True) -> list[dict]:
        """Returns all active tags with their document counts (doc_count > 0)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT t.id, t.name, t.normalized_name, COUNT(dt.document_id) AS doc_count
                FROM tags t
                JOIN document_tags dt ON t.id = dt.tag_id
                GROUP BY t.id
                HAVING doc_count > 0
                ORDER BY doc_count DESC, t.name ASC
            """ if only_active else """
                SELECT t.id, t.name, t.normalized_name, COUNT(dt.document_id) AS doc_count
                FROM tags t
                LEFT JOIN document_tags dt ON t.id = dt.tag_id
                GROUP BY t.id
                ORDER BY doc_count DESC, t.name ASC
            """
            cursor.execute(query)
            return [dict(r) for r in cursor.fetchall()]

    def search_documents_by_tag(self, tag_name: str) -> list[str]:
        """Returns list of absolute file paths tagged with `tag_name`."""
        clean_tag = tag_name.strip().lstrip("#")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.path
                FROM documents d
                JOIN document_tags dt ON d.id = dt.document_id
                JOIN tags t ON dt.tag_id = t.id
                WHERE t.name = ? OR t.normalized_name = ?
                ORDER BY d.title ASC
            """, (clean_tag, clean_tag.lower()))
            return [r["path"] for r in cursor.fetchall()]

    # ── Wikilink & Backlink Engine ─────────────────────────────────────────────

    def resolve_target_document(self, raw_target: str, source_path: Optional[str] = None, workspace_folder: Optional[str] = None) -> Optional[dict]:
        """
        Resolves a wikilink or markdown link target string to a document record.
        Supports:
        - Note Title: 'README', 'Kế Hoạch'
        - Direct Relative Path: 'archive/20260729_refactoring_summary.md'
        - Stem Name: '20260729_refactoring_summary'
        Uses Proximity Priority: prefers file in the same directory as source_path if duplicate titles exist.
        """
        clean_target = raw_target.strip().replace("%20", " ")
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 0. Try direct relative path resolution from source_path
            if source_path:
                source_dir = os.path.dirname(os.path.normpath(os.path.abspath(source_path)))
                cand = os.path.normpath(os.path.abspath(os.path.join(source_dir, clean_target)))
                if os.path.exists(cand) and os.path.isfile(cand):
                    cursor.execute("SELECT * FROM documents WHERE path = ?", (cand,))
                    row = cursor.fetchone()
                    if row:
                        return dict(row)
                if not cand.endswith(".md"):
                    cand_md = cand + ".md"
                    if os.path.exists(cand_md) and os.path.isfile(cand_md):
                        cursor.execute("SELECT * FROM documents WHERE path = ?", (cand_md,))
                        row = cursor.fetchone()
                        if row:
                            return dict(row)

            # Extract stem if raw_target ends with extension
            target_stem = clean_target
            if target_stem.lower().endswith(".markdown"):
                target_stem = target_stem[:-9]
            elif target_stem.lower().endswith(".md"):
                target_stem = target_stem[:-3]
            target_stem = target_stem.split("/")[-1].split("\\")[-1]

            # 1. Exact match by Title or Filename (without .md) - supporting both Windows (\) and Unix (/) separators
            cursor.execute("""
                SELECT * FROM documents 
                WHERE title = ? OR title = ? OR path LIKE ? OR path LIKE ?
            """, (target_stem, clean_target, f"%{os.sep}{target_stem}.md", f"%/{target_stem}.md"))
            raw_rows = cursor.fetchall()

            if not raw_rows:
                # 2. Case-insensitive exact match
                cursor.execute("""
                    SELECT * FROM documents 
                    WHERE LOWER(title) = LOWER(?) OR LOWER(title) = LOWER(?)
                """, (target_stem, clean_target))
                raw_rows = cursor.fetchall()

            # Prioritize candidates that currently exist on disk
            existing_rows = [r for r in raw_rows if os.path.exists(r["path"])]
            rows = existing_rows if existing_rows else raw_rows

            if not rows:
                return None

            if len(rows) == 1:
                return dict(rows[0])

            # Disambiguation: Proximity Priority (same directory as source_path)
            if source_path:
                source_dir = os.path.dirname(os.path.normpath(os.path.abspath(source_path)))
                for r in rows:
                    r_dir = os.path.dirname(r["path"])
                    if r_dir == source_dir:
                        return dict(r)

            # Fallback: First matched candidate from query results
            return dict(rows[0])

    def set_document_wikilinks(self, source_id: str, wikilinks: list[WikilinkToken], source_path: Optional[str] = None) -> None:
        """Parses and updates all wikilinks originating from a source document."""
        with self._write_lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM wikilinks WHERE source_id = ?", (source_id,))

                for wl in wikilinks:
                    target_doc = self.resolve_target_document(wl.raw_target, source_path=source_path)
                    target_id = target_doc["id"] if target_doc else None
                    resolved = 1 if target_id else 0

                    cursor.execute("""
                        INSERT INTO wikilinks (
                            source_id, target_id, target_title_raw, display_text, snippet, resolved
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (source_id, target_id, wl.raw_target, wl.display_text, wl.snippet, resolved))

                conn.commit()

    def re_resolve_broken_wikilinks(self, new_doc_id: str, new_doc_title: str) -> int:
        """
        Re-resolves broken wikilinks across all notes when a new file is created.
        Matches exact target_title_raw as well as Vietnamese normalized fuzzy match.
        """
        from src.services.fuzzy_matcher import normalize_vietnamese

        clean_title = new_doc_title.strip()
        norm_title = normalize_vietnamese(clean_title)
        affected = 0

        with self._write_lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # 1. Exact title match (fast SQL)
                cursor.execute("""
                    UPDATE wikilinks 
                    SET target_id = ?, resolved = 1 
                    WHERE (LOWER(target_title_raw) = LOWER(?) OR target_title_raw = ?) 
                      AND resolved = 0
                """, (new_doc_id, clean_title, clean_title))
                affected += cursor.rowcount

                # 2. Vietnamese Normalized Fuzzy Match for remaining unresolved links
                cursor.execute("SELECT id, target_title_raw FROM wikilinks WHERE resolved = 0")
                unresolved = cursor.fetchall()
                for row in unresolved:
                    wl_id = row["id"]
                    raw_target = row["target_title_raw"]
                    if normalize_vietnamese(raw_target) == norm_title:
                        cursor.execute("UPDATE wikilinks SET target_id = ?, resolved = 1 WHERE id = ?", (new_doc_id, wl_id))
                        affected += 1

                conn.commit()
                return affected

    def get_linked_references(self, target_doc_id: str, workspace_folder: Optional[str] = None) -> list[dict]:
        """
        Returns all source documents that contain resolved wikilinks pointing to `target_doc_id`.
        Includes snippets, source titles, and relative paths for disambiguation.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT w.id AS wikilink_id, w.snippet, w.display_text, w.target_title_raw,
                       d.id AS source_id, d.title AS source_title, d.path AS source_path
                FROM wikilinks w
                JOIN documents d ON w.source_id = d.id
                WHERE w.target_id = ? AND w.resolved = 1
                ORDER BY d.title ASC
            """, (target_doc_id,))
            results = []
            for r in cursor.fetchall():
                item = dict(r)
                if workspace_folder and item.get("source_path"):
                    try:
                        item["relative_path"] = os.path.relpath(item["source_path"], workspace_folder)
                    except ValueError:
                        item["relative_path"] = os.path.basename(item["source_path"])
                else:
                    item["relative_path"] = os.path.basename(item.get("source_path", ""))
                results.append(item)
            return results

    def get_unlinked_mentions(self, target_doc_id: str, target_title: str, workspace_folder: Optional[str] = None) -> list[dict]:
        """
        Scans other documents in workspace for textual mentions of `target_title` without [[...]].
        """
        if not target_title or len(target_title) < 2:
            return []

        results = []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Get other documents
            cursor.execute("SELECT id, title, path FROM documents WHERE id != ?", (target_doc_id,))
            other_docs = [dict(r) for r in cursor.fetchall()]

        for doc in other_docs:
            doc_path = doc["path"]
            if os.path.exists(doc_path):
                try:
                    with open(doc_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    mentions = find_unlinked_mentions(content, target_title)
                    for m in mentions:
                        rel_path = os.path.basename(doc_path)
                        if workspace_folder:
                            try:
                                rel_path = os.path.relpath(doc_path, workspace_folder)
                            except ValueError:
                                pass
                        results.append({
                            "source_id": doc["id"],
                            "source_title": doc["title"],
                            "source_path": doc_path,
                            "relative_path": rel_path,
                            "matched_text": m.matched_text,
                            "snippet": m.snippet,
                            "start_pos": m.start_pos,
                            "end_pos": m.end_pos,
                        })
                except Exception as ex:
                    print(f"[MetadataIndex] Failed to read {doc_path} for mentions: {ex}")

        return results

    # ── 3-Way Sync Engine ──────────────────────────────────────────────────────

    def sync_workspace_incremental(
        self,
        workspace_folder: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> dict:
        """
        Comprehensive 3-Way Synchronization:
        1. Filesystem scan for markdown files (.md).
        2. Orphan record cleanup (removes records from DB for files deleted on disk).
        3. Incremental hash diffing (only reads/parses files with changed SHA-256).
        Wrapped in a single atomic transaction with write lock to prevent half-updated state on crash.
        """
        from src.services.fuzzy_matcher import normalize_vietnamese

        if not workspace_folder or not os.path.isdir(workspace_folder):
            return {"added": 0, "updated": 0, "deleted": 0, "total": 0}

        norm_ws = os.path.normpath(os.path.abspath(workspace_folder))

        # 1. Discover all disk files
        disk_files: list[str] = []
        for root, dirs, files in os.walk(norm_ws):
            # Skip hidden folders and virtual environments (.git, .agents, venv, node_modules, build caches)
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "dist", "build", "__pycache__", "venv", ".venv", "env", ".env")]
            for f in files:
                if f.lower().endswith(".md"):
                    disk_files.append(os.path.normpath(os.path.abspath(os.path.join(root, f))))

        total_files = len(disk_files)
        disk_files_set = set(disk_files)
        stats = {"added": 0, "updated": 0, "deleted": 0, "total": total_files}

        # 2. Execute Orphan Purge + Incremental Upserts in SINGLE ATOMIC TRANSACTION
        with self._write_lock:
            with self.get_connection() as conn:
                with conn:  # SQLite context manager manages BEGIN/COMMIT/ROLLBACK atomically
                    cursor = conn.cursor()

                    disk_files_norm_set = {os.path.normpath(os.path.abspath(f)).lower() for f in disk_files}

                    # Find all existing DB records in this workspace reliably across all OS path formats
                    cursor.execute("SELECT id, path, content_hash FROM documents")
                    all_rows = cursor.fetchall()
                    db_records = {}
                    for r in all_rows:
                        p = r["path"]
                        try:
                            norm_p = os.path.normpath(os.path.abspath(p))
                            if os.path.commonpath([norm_p, norm_ws]) == norm_ws:
                                db_records[norm_p.lower()] = {"id": r["id"], "path": p, "content_hash": r["content_hash"]}
                        except Exception:
                            pass

                    # 2a. Orphan Purge (files in DB but not on disk)
                    orphan_items = [item for k, item in db_records.items() if k not in disk_files_norm_set or not os.path.exists(item["path"])]
                    if orphan_items:
                        cursor.executemany("DELETE FROM documents WHERE id = ?", [(item["id"],) for item in orphan_items])
                        stats["deleted"] = len(orphan_items)

                    # 2b. Incremental Scan & Upsert
                    for idx, file_path in enumerate(disk_files, start=1):
                        if progress_callback:
                            progress_callback(idx, total_files, os.path.basename(file_path))

                        norm_file_path = os.path.normpath(os.path.abspath(file_path))
                        try:
                            with open(norm_file_path, "r", encoding="utf-8", errors="replace") as f:
                                content = f.read()

                            new_hash = self.calculate_hash(content)
                            db_entry = db_records.get(norm_file_path.lower())

                            # Skip parsing if hash is unchanged
                            if db_entry and db_entry["content_hash"] == new_hash:
                                continue

                            # Extract Title
                            title = os.path.splitext(os.path.basename(norm_file_path))[0]
                            first_heading_m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                            if first_heading_m:
                                raw_h1 = first_heading_m.group(1).strip()
                                clean_h1 = re.sub(r'[*_`]', '', raw_h1)
                                clean_h1 = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean_h1).strip()
                                if clean_h1:
                                    title = clean_h1

                            # Upsert document in current transaction
                            if db_entry:
                                doc_id = db_entry["id"]
                                cursor.execute("""
                                    UPDATE documents 
                                    SET title = ?, content_hash = ?, updated_at = CURRENT_TIMESTAMP 
                                    WHERE id = ?
                                """, (title, new_hash, doc_id))
                                stats["updated"] += 1
                            else:
                                doc_id = str(uuid.uuid4())
                                cursor.execute("""
                                    INSERT INTO documents (id, path, title, content_hash)
                                    VALUES (?, ?, ?, ?)
                                    ON CONFLICT(path) DO UPDATE SET
                                        title = excluded.title,
                                        content_hash = excluded.content_hash,
                                        updated_at = CURRENT_TIMESTAMP
                                """, (doc_id, norm_file_path, title, new_hash))
                                cursor.execute("SELECT id FROM documents WHERE path = ? COLLATE NOCASE", (norm_file_path,))
                                r_id = cursor.fetchone()
                                if r_id:
                                    doc_id = r_id["id"]
                                stats["added"] += 1

                            # Sync Tags
                            tags = extract_tags(content)
                            cursor.execute("DELETE FROM document_tags WHERE document_id = ?", (doc_id,))
                            for tag in tags:
                                clean_tag = tag.strip().lstrip("#")
                                if not clean_tag:
                                    continue
                                norm_tag = normalize_vietnamese(clean_tag).replace(" ", "-")
                                cursor.execute("""
                                    INSERT INTO tags (name, normalized_name)
                                    VALUES (?, ?)
                                    ON CONFLICT(name) DO UPDATE SET normalized_name = excluded.normalized_name
                                """, (clean_tag, norm_tag))
                                cursor.execute("SELECT id FROM tags WHERE name = ?", (clean_tag,))
                                tag_row = cursor.fetchone()
                                if tag_row:
                                    cursor.execute("""
                                        INSERT OR IGNORE INTO document_tags (document_id, tag_id)
                                        VALUES (?, ?)
                                    """, (doc_id, tag_row["id"]))

                            # Sync Wikilinks
                            wikilinks = extract_wikilinks(content)
                            cursor.execute("DELETE FROM wikilinks WHERE source_id = ?", (doc_id,))
                            for wl in wikilinks:
                                clean_target = wl.raw_target.strip()
                                # Resolve target candidate in current transaction cursor.
                                # Known limitation: bulk incremental sync prioritizes exact/case-insensitive match
                                # without directory proximity disambiguation to maintain high transaction throughput.
                                cursor.execute("""
                                    SELECT id FROM documents 
                                    WHERE title = ? OR path LIKE ? OR path LIKE ?
                                """, (clean_target, f"%{os.sep}{clean_target}.md", f"%/{clean_target}.md"))
                                t_row = cursor.fetchone()
                                if not t_row:
                                    cursor.execute("""
                                        SELECT id FROM documents 
                                        WHERE LOWER(title) = LOWER(?)
                                    """, (clean_target,))
                                    t_row = cursor.fetchone()

                                target_id = t_row["id"] if t_row else None
                                resolved = 1 if target_id else 0

                                cursor.execute("""
                                    INSERT INTO wikilinks (
                                        source_id, target_id, target_title_raw, display_text, snippet, resolved
                                    ) VALUES (?, ?, ?, ?, ?, ?)
                                """, (doc_id, target_id, wl.raw_target, wl.display_text, wl.snippet, resolved))

                            # Re-resolve broken links pointing to this note
                            norm_doc_title = normalize_vietnamese(title)
                            cursor.execute("""
                                UPDATE wikilinks 
                                SET target_id = ?, resolved = 1 
                                WHERE (LOWER(target_title_raw) = LOWER(?) OR target_title_raw = ?) 
                                  AND resolved = 0
                            """, (doc_id, title.strip(), title.strip()))

                            cursor.execute("SELECT id, target_title_raw FROM wikilinks WHERE resolved = 0")
                            for u_row in cursor.fetchall():
                                if normalize_vietnamese(u_row["target_title_raw"]) == norm_doc_title:
                                    cursor.execute("UPDATE wikilinks SET target_id = ?, resolved = 1 WHERE id = ?", (doc_id, u_row["id"]))

                        except Exception as ex:
                            print(f"[MetadataIndex] Error syncing file {file_path}: {ex}")

                # Purge orphan tags that are no longer referenced by any document
                cursor.execute("DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM document_tags)")

        return stats

    def get_wikilink_suggestions(
        self,
        query: str = "",
        workspace_folder: Optional[str] = None,
        limit: int = 15,
    ) -> list[dict]:
        """
        Returns ranked document suggestions for wikilink autocomplete matching `query`.
        Uses normalized Vietnamese fuzzy matching and multi-tier relevance ranking:
        1. Exact match on title (score 100)
        2. Exact normalized match on title (score 95)
        3. Prefix match on title (score 85)
        4. Word token prefix match on title (score 70)
        5. Substring containment (score 50)
        6. Fuzzy Token/Sequence similarity (score 35-65)
        """
        from src.services.fuzzy_matcher import normalize_vietnamese, calculate_similarity

        clean_q = query.strip()
        norm_q = normalize_vietnamese(clean_q)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            if workspace_folder:
                norm_ws = os.path.normpath(os.path.abspath(workspace_folder))
                cursor.execute("SELECT id, path, title FROM documents WHERE path LIKE ? ORDER BY updated_at DESC", (f"{norm_ws}%",))
            else:
                cursor.execute("SELECT id, path, title FROM documents ORDER BY updated_at DESC")
            rows = cursor.fetchall()

        # Fallback: if database has 0 documents for this folder, scan folder on disk immediately
        if not rows and workspace_folder and os.path.isdir(workspace_folder):
            norm_ws = os.path.normpath(os.path.abspath(workspace_folder))
            disk_rows = []
            for root, dirs, files in os.walk(norm_ws):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "dist", "build", "__pycache__", "venv", ".venv")]
                for f in files:
                    if f.lower().endswith(".md"):
                        full_p = os.path.normpath(os.path.abspath(os.path.join(root, f)))
                        title = os.path.splitext(f)[0]
                        disk_rows.append({"id": full_p, "path": full_p, "title": title})
                if len(disk_rows) >= 30:
                    break
            rows = disk_rows

        candidates = []
        for r in rows:
            doc_id = r["id"]
            doc_path = r["path"]
            title = r["title"]
            rel_path = os.path.basename(doc_path)
            if workspace_folder:
                try:
                    rel_path = os.path.relpath(doc_path, workspace_folder)
                except ValueError:
                    pass

            if not clean_q:
                # Return most recently updated docs if query is empty
                candidates.append({
                    "id": doc_id,
                    "title": title,
                    "path": doc_path,
                    "relative_path": rel_path,
                    "score": 50,
                })
                continue

            norm_title = normalize_vietnamese(title)
            score = 0

            if title == clean_q:
                score = 100
            elif norm_title == norm_q:
                score = 95
            elif norm_title.startswith(norm_q):
                score = 85
            elif any(w.startswith(norm_q) for w in norm_title.split()):
                score = 70
            elif norm_q in norm_title or norm_q in normalize_vietnamese(rel_path):
                score = 50
            else:
                sim = calculate_similarity(clean_q, title)
                if sim >= 0.45:
                    score = int(sim * 65)

            if score > 0:
                candidates.append({
                    "id": doc_id,
                    "title": title,
                    "path": doc_path,
                    "relative_path": rel_path,
                    "score": score,
                })

        candidates.sort(key=lambda x: (-x["score"], len(x["title"]), x["title"].lower()))
        return candidates[:limit]

    def get_tag_suggestions(
        self,
        query: str = "",
        limit: int = 15,
    ) -> list[dict]:
        """
        Returns ranked tag suggestions for tag autocomplete matching `query`.
        """
        from src.services.fuzzy_matcher import normalize_vietnamese

        clean_q = query.strip().lstrip("#")
        norm_q = normalize_vietnamese(clean_q)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.id, t.name, t.normalized_name, COUNT(dt.document_id) as doc_count
                FROM tags t
                LEFT JOIN document_tags dt ON t.id = dt.tag_id
                GROUP BY t.id, t.name, t.normalized_name
                ORDER BY doc_count DESC, t.name ASC
            """)
            rows = cursor.fetchall()

        candidates = []
        for r in rows:
            name = r["name"]
            norm_name = r["normalized_name"] or normalize_vietnamese(name)
            doc_count = r["doc_count"]

            if not clean_q:
                candidates.append({
                    "name": name,
                    "doc_count": doc_count,
                    "score": 50,
                })
                continue

            score = 0
            if norm_name == norm_q:
                score = 100
            elif norm_name.startswith(norm_q):
                score = 80
            elif norm_q in norm_name:
                score = 40

            if score > 0:
                candidates.append({
                    "name": name,
                    "doc_count": doc_count,
                    "score": score,
                })

        candidates.sort(key=lambda x: (-x["score"], -x["doc_count"], x["name"].lower()))
        return candidates[:limit]



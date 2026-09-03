import os
import hashlib
import shutil
from typing import Callable

PREVIEW_MEDIA_DIR_NAME = "preview_media"


class MediaAssetManager:
    _instance = None
    _cleanup_hooks: list[Callable[[str], None]] = []

    PREVIEW_MEDIA_DIR_NAME = PREVIEW_MEDIA_DIR_NAME

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MediaAssetManager, cls).__new__(cls, *args, **kwargs)
            cls._instance._init_manager()
        return cls._instance

    @classmethod
    def register_cleanup_hook(cls, hook: Callable[[str], None]):
        """Registers a callback hook fn(session_id: str) invoked when a session is cleared."""
        if hook not in cls._cleanup_hooks:
            cls._cleanup_hooks.append(hook)

    def _init_manager(self):
        # Resolve AppData cache directory
        appdata_dir = os.getenv('APPDATA')
        if not appdata_dir:
            appdata_dir = os.path.join(os.path.expanduser("~"), ".config")
        self.cache_dir = os.path.join(appdata_dir, "DocConvert", "cache", PREVIEW_MEDIA_DIR_NAME)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.current_session_id = None
        self.current_session_dir = None
        self._session_hashes: dict[str, dict[str, str]] = {}  # session_id -> {hash: path}

    def set_active_session(self, session_id: str):
        """Sets the active session ID and creates its cache folder."""
        if not session_id:
            return
        self.current_session_id = session_id
        self.current_session_dir = os.path.join(self.cache_dir, session_id)
        os.makedirs(self.current_session_dir, exist_ok=True)
        if session_id not in self._session_hashes:
            self._session_hashes[session_id] = {}

    def clear_session(self, session_id: str):
        """Removes the cache folder for the specified session_id and notifies registered cleanup hooks."""
        if not session_id:
            return
        session_dir = os.path.join(self.cache_dir, session_id)
        if os.path.exists(session_dir):
            try:
                shutil.rmtree(session_dir)
            except Exception as e:
                print(f"[DEBUG] MediaAssetManager: Failed to remove session dir {session_dir}: {e}")
        self._session_hashes.pop(session_id, None)
        if self.current_session_id == session_id:
            self.current_session_id = None
            self.current_session_dir = None

        # Notify all registered cleanup hooks (e.g. preview base64 memory cache)
        for hook in self._cleanup_hooks:
            try:
                hook(session_id)
            except Exception as e:
                print(f"[WARNING] MediaAssetManager: Cleanup hook failed for session '{session_id}': {e}")
                try:
                    from src.utils.logger import log_error
                    log_error(e, context_info=f"MediaAssetManager.clear_session:{session_id}")
                except Exception:
                    pass

    def start_session(self, file_path: str) -> str:
        """
        Starts a new session by hashing the file's path + modification time + size.
        This provides a unique, stable, yet modifiable cache directory for this file.
        """
        import time
        try:
            mtime = os.path.getmtime(file_path)
            size = os.path.getsize(file_path)
        except Exception:
            mtime = time.time()
            size = 0

        key_str = f"{file_path}_{mtime}_{size}"
        session_id = hashlib.md5(key_str.encode('utf-8')).hexdigest()[:12]
        self.set_active_session(session_id)
        return session_id

    def open_session(self, file_path: str) -> str:
        """Opens/starts a session directory for the given file_path."""
        return self.start_session(file_path)

    def get_session_dir(self, session_id: str | None = None) -> str:
        """Returns the absolute path of the session's cache folder."""
        target_id = session_id or self.current_session_id
        if target_id:
            sdir = os.path.join(self.cache_dir, target_id)
            os.makedirs(sdir, exist_ok=True)
            return sdir

        if not self.current_session_dir:
            self.current_session_dir = os.path.join(self.cache_dir, "default")
            os.makedirs(self.current_session_dir, exist_ok=True)
        return self.current_session_dir

    def register_image(self, image_bytes: bytes, filename: str, dedup: bool = True, session_id: str | None = None) -> str:
        """
        Saves the image bytes to the session cache folder in AppData and returns an absolute file path.
        Automatically deduplicates identical images via MD5 content hash.
        """
        if not image_bytes:
            return ""

        target_sid = session_id or self.current_session_id or "default"
        if target_sid not in self._session_hashes:
            self._session_hashes[target_sid] = {}

        img_hash = None
        if dedup:
            img_hash = hashlib.md5(image_bytes).hexdigest()
            if img_hash in self._session_hashes[target_sid]:
                cached_path = self._session_hashes[target_sid][img_hash]
                if os.path.exists(cached_path):
                    return cached_path.replace("\\", "/")

        session_dir = self.get_session_dir(session_id=session_id)
        dest_path = os.path.join(session_dir, filename)
        try:
            with open(dest_path, "wb") as f:
                f.write(image_bytes)
            if dedup and img_hash:
                self._session_hashes[target_sid][img_hash] = dest_path
        except Exception as e:
            print(f"[DEBUG] MediaAssetManager: Failed to write image {filename}: {e}")
        return dest_path.replace("\\", "/")

    def resolve_uri(self, uri: str, base_dir: str = None, session_id: str | None = None) -> str:
        """
        Resolves a virtual URI (like @media/image_rId8.png) or relative path to its absolute cached disk path.
        Searches the current session directory first, then base_dir (if provided), then all cached session folders in AppData.
        """
        if not uri:
            return uri

        if uri.startswith("@media/"):
            filename = uri[7:]
            primary_path = os.path.normpath(os.path.join(self.get_session_dir(session_id=session_id), filename))
            return primary_path

        # If not @media/, check if it's already an existing file path or relative to base_dir or in cache_dir
        if not uri.startswith(("http://", "https://", "data:")):
            norm_uri = os.path.normpath(uri)
            if os.path.exists(norm_uri) and os.path.isfile(norm_uri):
                return norm_uri

            if base_dir:
                candidate = os.path.normpath(os.path.abspath(os.path.join(base_dir, uri)))
                if os.path.exists(candidate) and os.path.isfile(candidate):
                    return candidate

            # Priority 1: Check target session cache directory strictly without cross-session bleed
            base_name = os.path.basename(uri)
            session_cand = os.path.normpath(os.path.join(self.get_session_dir(session_id=session_id), base_name))
            if os.path.exists(session_cand) and os.path.isfile(session_cand):
                return session_cand

            # Priority 2: Smart Fallback: Check relative to CWD, Desktop, User home & their immediate subdirectories
            clean_rel = uri.lstrip("./").lstrip(".\\")
            search_bases = [
                os.getcwd(),
                os.path.dirname(os.getcwd()),
                os.path.expanduser("~/Desktop"),
            ]
            for sbase in search_bases:
                if sbase and os.path.exists(sbase):
                    cand = os.path.normpath(os.path.join(sbase, clean_rel))
                    if os.path.exists(cand) and os.path.isfile(cand):
                        return cand
                    try:
                        for item in os.listdir(sbase):
                            sub_dir = os.path.join(sbase, item)
                            if os.path.isdir(sub_dir):
                                cand_sub = os.path.normpath(os.path.join(sub_dir, clean_rel))
                                if os.path.exists(cand_sub) and os.path.isfile(cand_sub):
                                    return cand_sub
                    except Exception:
                        pass

        return uri

    def import_local_images(self, markdown_content: str, base_dir: str, session_id: str | None = None) -> str:
        """
        Finds local image file links or @media/ links in Markdown, registers/resolves them in AppData session cache,
        and rewrites them to absolute AppData file paths so images remain accessible from any Markdown viewer.
        """
        if not markdown_content or "![" not in markdown_content or "](" not in markdown_content:
            return markdown_content

        import re
        image_pattern = r"!\[([^\]]*)\]\((.+?\.(?:png|jpg|jpeg|gif|svg|webp|bmp|ico)|https?://\S+|@media/\S+?|[^\n)]+)\)"

        def replacer(match):
            alt = match.group(1)
            src = match.group(2)
            if src.startswith(("http://", "https://", "data:")):
                return match.group(0)

            resolved = self.resolve_uri(src, session_id=session_id)
            if os.path.exists(resolved) and os.path.isfile(resolved):
                abs_path = os.path.abspath(resolved).replace("\\", "/")
                return f"![{alt}]({abs_path})"

            local_path = src if os.path.isabs(src) else os.path.join(base_dir, src) if base_dir else src
            if os.path.exists(local_path) and os.path.isfile(local_path):
                try:
                    with open(local_path, "rb") as f:
                        img_bytes = f.read()
                    filename = os.path.basename(local_path)
                    registered_path = self.register_image(img_bytes, filename, session_id=session_id)
                    return f"![{alt}]({registered_path})"
                except Exception as e:
                    print(f"[DEBUG] MediaAssetManager: Failed to import local image {local_path}: {e}")
            return match.group(0)

        return re.sub(image_pattern, replacer, markdown_content)

    def export_assets(self, markdown_content: str, target_markdown_path: str, session_id: str | None = None) -> str:
        """
        Ensures all images referenced in Markdown content (both Markdown ![]() and HTML <img />)
        are copied into a relative `<doc_name>_assets` directory next to the target markdown file,
        rewriting image links to portable relative paths (`./<doc_name>_assets/filename.png`).
        Resolves both `@media/` cache URIs, session cache paths, and external absolute disk paths.
        """
        if not markdown_content or ("![" not in markdown_content and "<img" not in markdown_content and "@media/" not in markdown_content):
            return markdown_content

        import re

        target_dir = os.path.dirname(target_markdown_path)
        doc_stem = os.path.splitext(os.path.basename(target_markdown_path))[0]
        if not doc_stem or doc_stem == ".":
            doc_stem = "document"

        assets_dir_name = f"{doc_stem}_assets"
        assets_dir = os.path.join(target_dir, assets_dir_name)

        def _get_file_hash(filepath: str) -> str:
            try:
                hasher = hashlib.md5()
                with open(filepath, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        hasher.update(chunk)
                return hasher.hexdigest()
            except Exception:
                return ""

        copied_hashes: dict[str, str] = {}  # hash -> final_filename mapping

        def _copy_and_get_relative_path(src: str) -> str:
            if not src or src.startswith(("http://", "https://", "data:")):
                return src

            resolved = self.resolve_uri(src, session_id=session_id)
            if not os.path.exists(resolved) and target_dir:
                candidate = os.path.join(target_dir, src)
                if os.path.exists(candidate):
                    resolved = candidate

            if os.path.exists(resolved) and os.path.isfile(resolved):
                try:
                    os.makedirs(assets_dir, exist_ok=True)
                    src_hash = _get_file_hash(resolved)

                    # If this exact content hash was already copied to assets_dir in this run:
                    if src_hash and src_hash in copied_hashes:
                        final_filename = copied_hashes[src_hash]
                        return f"./{assets_dir_name}/{final_filename}"

                    base_filename = os.path.basename(resolved)
                    name_stem, ext = os.path.splitext(base_filename)
                    final_filename = base_filename
                    dest_path = os.path.join(assets_dir, final_filename)

                    # Deduplicate collisions with different file contents
                    counter = 1
                    while os.path.exists(dest_path):
                        dest_hash = _get_file_hash(dest_path)
                        if src_hash and dest_hash == src_hash:
                            # Identical file already exists on disk
                            break
                        final_filename = f"{name_stem}_{counter}{ext}"
                        dest_path = os.path.join(assets_dir, final_filename)
                        counter += 1

                    if not os.path.exists(dest_path):
                        shutil.copy2(resolved, dest_path)

                    if src_hash:
                        copied_hashes[src_hash] = final_filename

                    return f"./{assets_dir_name}/{final_filename}"
                except Exception as e:
                    print(f"[DEBUG] MediaAssetManager: Failed to export asset '{resolved}': {e}")
                    return src

            return src

        def md_replacer(match):
            alt = match.group(1)
            src = match.group(2)
            new_src = _copy_and_get_relative_path(src)
            return f"![{alt}]({new_src})"

        def html_replacer(match):
            prefix = match.group(1)
            src = match.group(2)
            suffix = match.group(3)
            new_src = _copy_and_get_relative_path(src)
            return f"{prefix}{new_src}{suffix}"

        image_pattern = r"!\[([^\]]*)\]\((.+?\.(?:png|jpg|jpeg|gif|svg|webp|bmp|ico)|https?://\S+|@media/\S+?|[^\n)]+)\)"
        result = re.sub(image_pattern, md_replacer, markdown_content)

        html_pattern = r'(<img\s+[^>]*?src=["\'])([^"\']+)(["\'][^>]*?>)'
        result = re.sub(html_pattern, html_replacer, result, flags=re.IGNORECASE)

        return result

    DEFAULT_MAX_CACHE_BYTES = 200 * 1024 * 1024  # 200 MB

    def cleanup_cache(self, max_age_days: int = 7, protected_session_ids: set[str] | list[str] | None = None):
        """Removes session cache folders older than max_age_days and enforces LRU size limits."""
        import time
        if not os.path.exists(self.cache_dir):
            return
        now = time.time()
        max_age_sec = max_age_days * 24 * 60 * 60
        prot_set = set(protected_session_ids or [])
        for item in os.listdir(self.cache_dir):
            item_path = os.path.join(self.cache_dir, item)
            if os.path.isdir(item_path):
                # Skip protected sessions (e.g. any currently open tab)
                if item in prot_set or (self.current_session_id and item == self.current_session_id):
                    continue
                if self.current_session_dir and os.path.exists(self.current_session_dir):
                    try:
                        if os.path.samefile(item_path, self.current_session_dir):
                            continue
                    except Exception:
                        pass
                try:
                    mtime = os.path.getmtime(item_path)
                    if now - mtime > max_age_sec:
                        shutil.rmtree(item_path)
                except Exception as e:
                    print(f"[DEBUG] MediaAssetManager: Failed to clean cache dir {item_path}: {e}")
        self.enforce_lru_cache_limit(protected_session_ids=protected_session_ids)

    def enforce_lru_cache_limit(self, max_bytes: int = DEFAULT_MAX_CACHE_BYTES, protected_session_ids: set[str] | list[str] | None = None):
        """Purges oldest cached sessions until total cache size is under max_bytes, protecting active and background open tabs."""
        if not os.path.exists(self.cache_dir):
            return

        sessions = []
        total_size = 0
        prot_set = set(protected_session_ids or [])

        for item in os.listdir(self.cache_dir):
            item_path = os.path.join(self.cache_dir, item)
            if os.path.isdir(item_path):
                try:
                    dir_size = sum(
                        os.path.getsize(os.path.join(root, f))
                        for root, _, files in os.walk(item_path)
                        for f in files
                    )
                    atime = os.path.getmtime(item_path)
                    sessions.append((item, item_path, dir_size, atime))
                    total_size += dir_size
                except Exception:
                    pass

        # Sort by access/modification time ascending (oldest first)
        sessions.sort(key=lambda x: x[3])

        for session_name, path, size, _ in sessions:
            if total_size <= max_bytes:
                break
            # Skip removing currently active session and protected background tabs
            if session_name in prot_set or (self.current_session_id and session_name == self.current_session_id):
                continue
            if self.current_session_dir and os.path.exists(self.current_session_dir):
                try:
                    if os.path.samefile(path, self.current_session_dir):
                        continue
                except Exception:
                    pass
            try:
                shutil.rmtree(path)
                total_size -= size
            except Exception as e:
                print(f"[DEBUG] MediaAssetManager: LRU purge failed for {path}: {e}")

    def cleanup_old_sessions(self, max_age_days: int = 7, protected_session_ids: set[str] | list[str] | None = None):
        """Removes session cache folders older than max_age_days."""
        self.cleanup_cache(max_age_days=max_age_days, protected_session_ids=protected_session_ids)


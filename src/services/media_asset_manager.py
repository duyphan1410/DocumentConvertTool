import os
import hashlib
import shutil

class MediaAssetManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MediaAssetManager, cls).__new__(cls, *args, **kwargs)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self):
        # Resolve AppData cache directory
        appdata_dir = os.getenv('APPDATA')
        if not appdata_dir:
            appdata_dir = os.path.join(os.path.expanduser("~"), ".config")
        self.cache_dir = os.path.join(appdata_dir, "DocConvert", "cache", "preview_media")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.current_session_id = None
        self.current_session_dir = None

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
        self.current_session_id = hashlib.md5(key_str.encode('utf-8')).hexdigest()[:12]
        self.current_session_dir = os.path.join(self.cache_dir, self.current_session_id)
        os.makedirs(self.current_session_dir, exist_ok=True)
        return self.current_session_id

    def open_session(self, file_path: str) -> str:
        """Opens/starts a session directory for the given file_path."""
        return self.start_session(file_path)

    def get_session_dir(self) -> str:
        """Returns the absolute path of the current session's cache folder."""
        if not self.current_session_dir:
            self.current_session_dir = os.path.join(self.cache_dir, "default")
            os.makedirs(self.current_session_dir, exist_ok=True)
        return self.current_session_dir

    def register_image(self, image_bytes: bytes, filename: str) -> str:
        """
        Saves the image bytes to the session cache folder in AppData and returns an absolute file path.
        """
        session_dir = self.get_session_dir()
        dest_path = os.path.join(session_dir, filename)
        try:
            with open(dest_path, "wb") as f:
                f.write(image_bytes)
        except Exception as e:
            print(f"[DEBUG] MediaAssetManager: Failed to write image {filename}: {e}")
        return dest_path.replace("\\", "/")

    def resolve_uri(self, uri: str) -> str:
        """
        Resolves a virtual URI (like @media/image_rId8.png) or relative path to its absolute cached disk path.
        Searches the current session directory first, then all cached session folders in AppData.
        """
        if not uri:
            return uri

        if uri.startswith("@media/"):
            filename = uri[7:]
            primary_path = os.path.join(self.get_session_dir(), filename)
            if os.path.exists(primary_path) and os.path.isfile(primary_path):
                return primary_path

            # Search across all session directories in AppData cache
            if os.path.exists(self.cache_dir):
                for root, _, files in os.walk(self.cache_dir):
                    if filename in files:
                        found_path = os.path.join(root, filename)
                        if os.path.isfile(found_path):
                            return found_path

            return primary_path

        # If not @media/, check if it's already an existing file path or in cache_dir
        if not uri.startswith(("http://", "https://", "data:")):
            if os.path.exists(uri) and os.path.isfile(uri):
                return uri

            base_name = os.path.basename(uri)
            if os.path.exists(self.cache_dir):
                for root, _, files in os.walk(self.cache_dir):
                    if base_name in files:
                        found_path = os.path.join(root, base_name)
                        if os.path.isfile(found_path):
                            return found_path

        return uri

    def import_local_images(self, markdown_content: str, base_dir: str) -> str:
        """
        Finds local image file links or @media/ links in Markdown, registers/resolves them in AppData session cache,
        and rewrites them to absolute AppData file paths so images remain accessible from any Markdown viewer.
        """
        if not markdown_content or "![" not in markdown_content or "](" not in markdown_content:
            return markdown_content

        import re
        image_pattern = r"!\[([^\]]*)\]\(([^)]+)\)"

        def replacer(match):
            alt = match.group(1)
            src = match.group(2)
            if src.startswith(("http://", "https://", "data:")):
                return match.group(0)

            resolved = self.resolve_uri(src)
            if os.path.exists(resolved) and os.path.isfile(resolved):
                abs_path = os.path.abspath(resolved).replace("\\", "/")
                return f"![{alt}]({abs_path})"

            local_path = src if os.path.isabs(src) else os.path.join(base_dir, src) if base_dir else src
            if os.path.exists(local_path) and os.path.isfile(local_path):
                try:
                    with open(local_path, "rb") as f:
                        img_bytes = f.read()
                    filename = os.path.basename(local_path)
                    registered_path = self.register_image(img_bytes, filename)
                    return f"![{alt}]({registered_path})"
                except Exception as e:
                    print(f"[DEBUG] MediaAssetManager: Failed to import local image {local_path}: {e}")
            return match.group(0)

        return re.sub(image_pattern, replacer, markdown_content)

    def export_assets(self, markdown_content: str, target_markdown_path: str) -> str:
        """
        Ensures all images referenced in Markdown content are safely stored in AppData cache
        and saved with absolute AppData paths so no local _media folders need to be created.
        """
        if not markdown_content:
            return markdown_content

        base_dir = os.path.dirname(target_markdown_path)
        return self.import_local_images(markdown_content, base_dir)

    DEFAULT_MAX_CACHE_BYTES = 200 * 1024 * 1024  # 200 MB

    def cleanup_cache(self, max_age_days: int = 7):
        """Removes session cache folders older than max_age_days and enforces LRU size limits."""
        import time
        if not os.path.exists(self.cache_dir):
            return
        now = time.time()
        max_age_sec = max_age_days * 24 * 60 * 60
        for item in os.listdir(self.cache_dir):
            item_path = os.path.join(self.cache_dir, item)
            if os.path.isdir(item_path):
                try:
                    mtime = os.path.getmtime(item_path)
                    if now - mtime > max_age_sec:
                        shutil.rmtree(item_path)
                except Exception as e:
                    print(f"[DEBUG] MediaAssetManager: Failed to clean cache dir {item_path}: {e}")
        self.enforce_lru_cache_limit()

    def enforce_lru_cache_limit(self, max_bytes: int = DEFAULT_MAX_CACHE_BYTES):
        """Purges oldest cached sessions until total cache size is under max_bytes."""
        if not os.path.exists(self.cache_dir):
            return

        sessions = []
        total_size = 0

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
                    sessions.append((item_path, dir_size, atime))
                    total_size += dir_size
                except Exception:
                    pass

        # Sort by access/modification time ascending (oldest first)
        sessions.sort(key=lambda x: x[2])

        for path, size, _ in sessions:
            if total_size <= max_bytes:
                break
            # Skip removing currently active session
            if self.current_session_dir and os.path.samefile(path, self.current_session_dir):
                continue
            try:
                shutil.rmtree(path)
                total_size -= size
            except Exception as e:
                print(f"[DEBUG] MediaAssetManager: LRU purge failed for {path}: {e}")

    def cleanup_old_sessions(self, max_age_days: int = 7):
        """Removes session cache folders older than max_age_days."""
        self.cleanup_cache(max_age_days=max_age_days)


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
        Saves the image bytes to the session cache folder and returns a virtual path
        prefix @media/<filename> to prevent local file paths in the editor.
        """
        session_dir = self.get_session_dir()
        dest_path = os.path.join(session_dir, filename)
        try:
            with open(dest_path, "wb") as f:
                f.write(image_bytes)
        except Exception as e:
            print(f"[DEBUG] MediaAssetManager: Failed to write image {filename}: {e}")
        return f"@media/{filename}"

    def resolve_uri(self, uri: str) -> str:
        """
        Resolves a virtual URI (like @media/image_rId8.png) to its absolute cached disk path.
        If it's not a virtual URI, returns the original string unchanged.
        """
        if uri and uri.startswith("@media/"):
            filename = uri[7:]
            return os.path.join(self.get_session_dir(), filename)
        return uri

    def export_assets(self, markdown_content: str, target_markdown_path: str) -> str:
        """
        Parses Markdown content, finds all referenced @media/ links, copies only the used
        cached files to a target local folder `<doc_name>_media/` next to target_markdown_path,
        and returns the markdown with relative links.
        """
        # Determine target media folder name and absolute path
        out_dir = os.path.dirname(target_markdown_path)
        out_base = os.path.splitext(os.path.basename(target_markdown_path))[0]
        dest_media_dir_name = f"{out_base}_media"
        dest_media_dir = os.path.join(out_dir, dest_media_dir_name)

        from src.core.converters import parse_inline

        # Retrieve all unique @media/ references from the content using structural parsing
        referenced_images = set()
        for line in markdown_content.splitlines():
            try:
                segments = parse_inline(line)
                for seg in segments:
                    if getattr(seg, "is_image", False) and seg.url and seg.url.startswith("@media/"):
                        referenced_images.add(seg.url)
            except Exception:
                pass

        if not referenced_images:
            return markdown_content

        # Copy the referenced images
        media_dir_created = False
        copied_mapping = {}

        for uri in referenced_images:
            filename = uri[7:]
            src_path = self.resolve_uri(uri)
            if os.path.exists(src_path) and os.path.isfile(src_path):
                if not media_dir_created:
                    os.makedirs(dest_media_dir, exist_ok=True)
                    media_dir_created = True
                dest_path = os.path.join(dest_media_dir, filename)
                try:
                    shutil.copy2(src_path, dest_path)
                    copied_mapping[uri] = f"{dest_media_dir_name}/{filename}"
                except Exception as e:
                    print(f"[DEBUG] MediaAssetManager: Failed to copy {src_path} to {dest_path}: {e}")

        # Rewrite references in the Markdown content
        rewritten_content = markdown_content
        for virtual_uri, relative_path in copied_mapping.items():
            rewritten_content = rewritten_content.replace(virtual_uri, relative_path)

        return rewritten_content

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


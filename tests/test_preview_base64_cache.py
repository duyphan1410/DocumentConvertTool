import os
import tempfile
import threading
import unittest
from PIL import Image

from src.services.media_asset_manager import MediaAssetManager, PREVIEW_MEDIA_DIR_NAME
from src.ui_flet.views.preview_view import (
    MAX_BASE64_CACHE_ENTRIES,
    _BASE64_CACHE,
    _BASE64_CACHE_LOCK,
    _resolve_session_id_from_path,
    image_to_base64_uri,
    purge_session_base64_cache,
    clear_base64_cache,
)


class TestPreviewBase64Cache(unittest.TestCase):
    def setUp(self):
        clear_base64_cache()
        self.temp_dir = tempfile.TemporaryDirectory()
        # Create a small dummy image for testing
        self.sample_img_path = os.path.join(self.temp_dir.name, "sample.png")
        img = Image.new("RGB", (200, 200), color=(73, 109, 137))
        img.save(self.sample_img_path)

    def tearDown(self):
        clear_base64_cache()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_auto_detect_session_id_windows_and_posix(self):
        """Verifies session_id auto-detection works with both Windows and POSIX separators."""
        # Windows style path
        win_path = rf"C:\Users\User\AppData\Local\DocConvert\cache\{PREVIEW_MEDIA_DIR_NAME}\tab_1\image.png"
        self.assertEqual(_resolve_session_id_from_path(win_path), "tab_1")

        # POSIX style path
        posix_path = f"/home/user/.config/DocConvert/cache/{PREVIEW_MEDIA_DIR_NAME}/tab_2/image.png"
        self.assertEqual(_resolve_session_id_from_path(posix_path), "tab_2")

        # External non-session path
        ext_path = r"C:\Users\User\Desktop\photos\avatar.jpg"
        self.assertEqual(_resolve_session_id_from_path(ext_path), "")

        # Explicit session_id override
        self.assertEqual(_resolve_session_id_from_path(win_path, session_id="custom_sid"), "custom_sid")

    def test_exact_session_purge(self):
        """Verifies purging tab_1 does NOT accidentally delete tab_10 or tab_11 (RFC-001 Issue #1)."""
        # Inject entries directly into cache
        with _BASE64_CACHE_LOCK:
            _BASE64_CACHE[("tab_1", "/path/a.png", 650, 70)] = "data:tab_1_a"
            _BASE64_CACHE[("tab_1", "/path/b.png", 650, 70)] = "data:tab_1_b"
            _BASE64_CACHE[("tab_10", "/path/c.png", 650, 70)] = "data:tab_10_c"
            _BASE64_CACHE[("tab_11", "/path/d.png", 650, 70)] = "data:tab_11_d"
            _BASE64_CACHE[("", "/path/ext.png", 650, 70)] = "data:ext"

        purge_session_base64_cache("tab_1")

        with _BASE64_CACHE_LOCK:
            # tab_1 entries must be gone
            self.assertNotIn(("tab_1", "/path/a.png", 650, 70), _BASE64_CACHE)
            self.assertNotIn(("tab_1", "/path/b.png", 650, 70), _BASE64_CACHE)

            # tab_10, tab_11 and un-namespaced entries must remain intact
            self.assertIn(("tab_10", "/path/c.png", 650, 70), _BASE64_CACHE)
            self.assertIn(("tab_11", "/path/d.png", 650, 70), _BASE64_CACHE)
            self.assertIn(("", "/path/ext.png", 650, 70), _BASE64_CACHE)

    def test_parameter_differentiation(self):
        """Verifies different target_width and quality produce distinct cache entries (RFC-001 Issue #2)."""
        uri_small = image_to_base64_uri(self.sample_img_path, target_width=100, quality=60, session_id="test_sess")
        uri_large = image_to_base64_uri(self.sample_img_path, target_width=800, quality=95, session_id="test_sess")

        self.assertTrue(uri_small.startswith("data:image/"))
        self.assertTrue(uri_large.startswith("data:image/"))

        with _BASE64_CACHE_LOCK:
            key_small = ("test_sess", self.sample_img_path, 100, 60)
            key_large = ("test_sess", self.sample_img_path, 800, 95)
            self.assertIn(key_small, _BASE64_CACHE)
            self.assertIn(key_large, _BASE64_CACHE)
            self.assertNotEqual(key_small, key_large)

    def test_lru_bounded_eviction(self):
        """Verifies cache size does not exceed MAX_BASE64_CACHE_ENTRIES and evicts least recently used."""
        total_items = 150
        for i in range(total_items):
            with _BASE64_CACHE_LOCK:
                key = (f"sess_{i}", f"/dummy/path_{i}.png", 650, 70)
                _BASE64_CACHE[key] = f"data:val_{i}"
                _BASE64_CACHE.move_to_end(key)
                while len(_BASE64_CACHE) > MAX_BASE64_CACHE_ENTRIES:
                    _BASE64_CACHE.popitem(last=False)

        with _BASE64_CACHE_LOCK:
            self.assertEqual(len(_BASE64_CACHE), MAX_BASE64_CACHE_ENTRIES)
            # Oldest entries (e.g. index 0, 1, 2) should be evicted
            self.assertNotIn(("sess_0", "/dummy/path_0.png", 650, 70), _BASE64_CACHE)
            # Recent entries should be present
            self.assertIn((f"sess_{total_items-1}", f"/dummy/path_{total_items-1}.png", 650, 70), _BASE64_CACHE)

    def test_observer_cleanup_hook_integration(self):
        """Verifies MediaAssetManager.clear_session triggers the registered purge hook and survives failing hooks."""
        mgr = MediaAssetManager()
        sid = "sess_hook_test"

        # Insert entry for sid
        with _BASE64_CACHE_LOCK:
            _BASE64_CACHE[(sid, "/path/img.png", 650, 70)] = "data:hook_test"

        # Register a failing hook to ensure fault tolerance
        failing_hook_ran = []
        def broken_hook(s):
            failing_hook_ran.append(s)
            raise RuntimeError("Simulated hook error")

        MediaAssetManager.register_cleanup_hook(broken_hook)

        # Clear session
        mgr.clear_session(sid)

        # Confirm failing hook was executed
        self.assertIn(sid, failing_hook_ran)

        # Confirm base64 cache was still purged despite broken hook
        with _BASE64_CACHE_LOCK:
            self.assertNotIn((sid, "/path/img.png", 650, 70), _BASE64_CACHE)

    def test_concurrency_thread_safety(self):
        """Verifies concurrent threads reading, writing, and purging cache do not raise errors."""
        errors = []

        def worker(thread_id: int):
            try:
                sid = f"tab_{thread_id % 5}"
                for i in range(30):
                    image_to_base64_uri(self.sample_img_path, target_width=50 + (i * 10), quality=70, session_id=sid)
                    if i % 10 == 0:
                        purge_session_base64_cache(sid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent operations caused errors: {errors}")


if __name__ == "__main__":
    unittest.main()

import unittest
import os
import shutil
import tempfile
from src.services.media_asset_manager import MediaAssetManager
from src.services.conversion_service import submit_async_task


class TestOptimizations(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_thread_pool_executor(self):
        def dummy_task(x, y):
            return x + y

        future = submit_async_task(dummy_task, 10, 20)
        result = future.result(timeout=2.0)
        self.assertEqual(result, 30)

    def test_lru_cache_manager(self):
        mgr = MediaAssetManager()
        self.assertIsNotNone(mgr.cache_dir)
        mgr.cleanup_cache(max_age_days=30)
        mgr.enforce_lru_cache_limit(max_bytes=100 * 1024 * 1024)



if __name__ == "__main__":
    unittest.main()

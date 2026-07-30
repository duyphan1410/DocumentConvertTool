"""
Layer 4: Headless Launch Test for DocumentConvertApp Flet GUI.
"""
import unittest
import sys
import os
import time
import subprocess

sys.path.insert(0, os.path.abspath("."))


class TestHeadlessLaunch(unittest.TestCase):
    def test_app_launch_without_crash(self):
        cmd = [sys.executable, "run.py"]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.abspath(".")
        )
        time.sleep(3)
        poll = proc.poll()

        if poll is not None:
            out, err = proc.communicate()
            err_msg = err.decode("utf-8", errors="ignore")
            self.fail(f"App terminated prematurely with code {poll}. STDERR:\n{err_msg}")
        else:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    unittest.main()

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
        time.sleep(3.5)
        poll = proc.poll()

        if poll is not None:
            out, err = proc.communicate()
            err_msg = err.decode("utf-8", errors="ignore")
            self.fail(f"App terminated prematurely with code {poll}. STDERR:\n{err_msg}")
        else:
            if sys.platform == "win32":
                subprocess.run(
                    f"taskkill /F /T /PID {proc.pid}",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                proc.kill()
            out, err = proc.communicate()
            err_text = err.decode("utf-8", errors="ignore")
            out_text = out.decode("utf-8", errors="ignore")
            if "Traceback" in err_text or "Unhandled error" in err_text or "TypeError" in err_text:
                self.fail(f"App printed errors during startup:\n{err_text}")
            if "Unhandled error in main()" in out_text or "Traceback" in out_text:
                self.fail(f"App printed errors in stdout:\n{out_text}")


if __name__ == "__main__":
    unittest.main()

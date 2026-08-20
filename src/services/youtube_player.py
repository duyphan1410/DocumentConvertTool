"""
Embedded In-App YouTube Player Service for DocConvert.
Uses Microsoft Edge WebView2 (pywebview) with a dedicated local HTTP server
sending valid HTTP Referer / strict-origin-when-cross-origin headers to eliminate YouTube Error 153.
Supports interactive timestamp seeking and video window re-use.
Adheres to the project Lazy Import standard.
"""
import os
import sys
import time
import json
import atexit
import subprocess
import threading
import http.server
import socketserver
import urllib.parse
from typing import Optional


PLAYER_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="referrer" content="strict-origin-when-cross-origin">
  <link rel="preconnect" href="https://www.youtube.com">
  <link rel="preconnect" href="https://googlevideo.com">
  <link rel="dns-prefetch" href="https://www.youtube.com">
  <link rel="dns-prefetch" href="https://googlevideo.com">
  <title>DocConvert - Video Player</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body {
      width: 100%;
      height: 100%;
      background: #000;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }
    #player-wrapper {
      flex: 1;
      width: 100%;
      height: 100%;
      background: #000;
      position: relative;
    }
    #player-frame {
      width: 100%;
      height: 100%;
      border: none;
    }
  </style>
</head>
<body>
  <div id="player-wrapper">
    <iframe id="player-frame"
            src="https://www.youtube.com/embed/__VIDEO_ID__?autoplay=1&start=__START_SEC__&enablejsapi=1&rel=0&playsinline=1"
            referrerpolicy="strict-origin-when-cross-origin"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowfullscreen>
    </iframe>
  </div>

  <script>
    function seekToTime(seconds) {
      var frame = document.getElementById('player-frame');
      if (frame && frame.contentWindow) {
        frame.contentWindow.postMessage(JSON.stringify({
          "event": "command",
          "func": "seekTo",
          "args": [seconds, true]
        }), "*");
        frame.contentWindow.postMessage(JSON.stringify({
          "event": "command",
          "func": "playVideo",
          "args": []
        }), "*");
      }
    }

    function loadVideo(videoId, seconds) {
      var frame = document.getElementById('player-frame');
      if (frame) {
        frame.src = "https://www.youtube.com/embed/" + videoId + "?autoplay=1&start=" + seconds + "&enablejsapi=1&rel=0&playsinline=1";
      }
    }
  </script>
</body>
</html>"""


class _PlayerHTTPHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        video_id = qs.get("v", [""])[0]
        start_sec = qs.get("t", ["0"])[0]

        html = PLAYER_HTML_TEMPLATE.replace("__VIDEO_ID__", video_id).replace("__START_SEC__", str(start_sec))

        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Suppress HTTP server console logs


def _force_window_foreground(window_title: str = ""):
    """Brings the player window to foreground Z-Index #1 using Win32 API without permanent pinning."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        import ctypes.wintypes

        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        HWND_TOPMOST = ctypes.wintypes.HWND(-1)
        HWND_NOTOPMOST = ctypes.wintypes.HWND(-2)
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_SHOWWINDOW = 0x0040

        found_hwnd = []

        def enum_win_proc(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value
            if "DocConvert - " in title or (window_title and window_title in title):
                found_hwnd.append(hwnd)
                return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_win_proc), 0)

        for hwnd in found_hwnd:
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)

            # Briefly toggle topmost to punch through Windows ForegroundLockTimeout
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)

            curr_fg = user32.GetForegroundWindow()
            attached = False
            fg_tid = 0
            target_tid = 0
            if curr_fg and curr_fg != hwnd:
                fg_tid = user32.GetWindowThreadProcessId(curr_fg, None)
                target_tid = user32.GetWindowThreadProcessId(hwnd, None)
                if fg_tid and target_tid and fg_tid != target_tid:
                    attached = bool(user32.AttachThreadInput(fg_tid, target_tid, True))

            try:
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                user32.SwitchToThisWindow(hwnd, True)
            finally:
                if attached:
                    user32.AttachThreadInput(fg_tid, target_tid, False)
    except Exception as e:
        print(f"[DEBUG] Window focus elevation error: {e}", file=sys.stderr)


def _run_player_subprocess():
    """Entry point executed when running this script as a standalone player process."""
    args = [a for a in sys.argv[1:] if a != "--youtube-player"]
    if not args:
        return

    video_id = args[0].strip()
    start_sec = int(args[1]) if len(args) > 1 else 0
    title_text = args[2] if len(args) > 2 else "YouTube In-App Player"

    # Enable automatic audio/video playback without requiring initial mouse click in WebView2
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--autoplay-policy=no-user-gesture-required"

    try:
        import webview
    except ImportError:
        import webbrowser
        browser_url = f"https://www.youtube.com/watch?v={video_id}"
        if start_sec > 0:
            browser_url += f"&t={start_sec}s"
        webbrowser.open(browser_url)
        return

    # Start local HTTP server with Referrer-Policy header to prevent Error 153
    server = socketserver.TCPServer(("127.0.0.1", 0), _PlayerHTTPHandler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    player_url = f"http://127.0.0.1:{port}/?v={video_id}&t={start_sec}"

    window = None

    def listen_stdin():
        nonlocal window
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                action = msg.get("action")
                if action == "seek" and window:
                    sec = msg.get("seconds", 0)
                    window.evaluate_js(f"seekToTime({sec});")
                    try:
                        window.restore()
                    except Exception:
                        pass
                    _force_window_foreground()
                elif action == "load" and window:
                    vid = msg.get("video_id", "").strip()
                    sec = msg.get("seconds", 0)
                    t = msg.get("title", "")
                    if t:
                        window.set_title(f"DocConvert - {t}")
                    window.evaluate_js(f"loadVideo('{vid}', {sec});")
                    try:
                        window.restore()
                    except Exception:
                        pass
                    _force_window_foreground(t)
                elif action == "close" and window:
                    window.destroy()
                    break
            except Exception as ex:
                print(f"[DEBUG] Player IPC error: {ex}", file=sys.stderr)

        # Parent process closed stdin or exited -> close player window immediately
        if window:
            try:
                window.destroy()
            except Exception:
                pass

    def on_shown():
        _force_window_foreground(title_text)

        def _stabilize_foreground():
            for delay in (0.10, 0.25):
                time.sleep(delay)
                _force_window_foreground(title_text)

        threading.Thread(target=_stabilize_foreground, daemon=True).start()
        t = threading.Thread(target=listen_stdin, daemon=True)
        t.start()

    win_w = 540
    win_h = 335
    pos_x = None
    pos_y = None

    if sys.platform == "win32":
        try:
            import ctypes
            import ctypes.wintypes
            rect = ctypes.wintypes.RECT()
            SPI_GETWORKAREA = 0x0030
            if ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
                # Top-left placement over editor buffer, leaving the entire right Preview / Transcript pane 100% visible
                pos_x = rect.left + 24
                pos_y = rect.top + 65
        except Exception:
            pos_x = 24
            pos_y = 65

    window = webview.create_window(
        title=f"DocConvert - {title_text}",
        url=player_url,
        width=win_w,
        height=win_h,
        x=pos_x,
        y=pos_y,
        resizable=True,
        on_top=False,
    )
    window.events.shown += on_shown
    try:
        webview.start()
    finally:
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass


class YouTubePlayerManager:
    """
    Singleton manager for controlling the in-app YouTube player window.
    Handles process creation, interactive timestamp seeking, and window re-use.
    """

    _instance: Optional["YouTubePlayerManager"] = None
    _proc: Optional[subprocess.Popen] = None
    _current_video_id: Optional[str] = None

    @classmethod
    def get_instance(cls) -> "YouTubePlayerManager":
        if cls._instance is None:
            cls._instance = YouTubePlayerManager()
        return cls._instance

    def is_running(self) -> bool:
        """Returns True if the player window process is currently alive."""
        if self._proc is None:
            return False
        if self._proc.poll() is not None:
            self._proc = None
            self._current_video_id = None
            return False
        return True

    def play(self, video_id: str, start_seconds: int = 0, title: str = ""):
        """
        Plays YouTube video in the in-app player window at specified start time.
        Re-uses existing player window if already open.
        """
        if not video_id:
            return

        clean_id = video_id.strip()
        display_title = title.strip() if title else f"YouTube ({clean_id})"

        # If player is already running
        if self.is_running() and self._proc and self._proc.stdin:
            try:
                if self._current_video_id == clean_id:
                    # Same video: seek directly to timestamp
                    payload = json.dumps({"action": "seek", "seconds": start_seconds}) + "\n"
                    self._proc.stdin.write(payload)
                    self._proc.stdin.flush()
                else:
                    # Different video: load new video URL
                    self._current_video_id = clean_id
                    payload = json.dumps({
                        "action": "load",
                        "video_id": clean_id,
                        "seconds": start_seconds,
                        "title": display_title,
                    }) + "\n"
                    self._proc.stdin.write(payload)
                    self._proc.stdin.flush()
                return
            except Exception as e:
                print(f"[DEBUG] Failed to send command to running player: {e}")
                self._proc = None

        # Check if pywebview is installed; fallback gracefully to browser if missing
        try:
            import webview  # noqa: F401
        except ImportError:
            import webbrowser
            browser_url = f"https://www.youtube.com/watch?v={clean_id}"
            if start_seconds > 0:
                browser_url += f"&t={start_seconds}s"
            webbrowser.open(browser_url)
            return

        # Start a new player subprocess
        self._current_video_id = clean_id
        if getattr(sys, "frozen", False):
            cmd = [
                sys.executable,
                "--youtube-player",
                clean_id,
                str(start_seconds),
                display_title,
            ]
        else:
            cmd = [
                sys.executable,
                "-u",
                os.path.abspath(__file__),
                clean_id,
                str(start_seconds),
                display_title,
            ]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            print(f"[DEBUG] Failed to launch YouTube player subprocess: {e}")

    def close(self):
        """Closes the player window if open."""
        if self.is_running() and self._proc and self._proc.stdin:
            try:
                self._proc.stdin.write(json.dumps({"action": "close"}) + "\n")
                self._proc.stdin.flush()
                self._proc.terminate()
            except Exception:
                pass
        self._proc = None
        self._current_video_id = None


# Auto-close player window on application exit
atexit.register(lambda: YouTubePlayerManager.get_instance().close())


if __name__ == "__main__":
    _run_player_subprocess()

"""
DocConvert Local Model Context Protocol (MCP) Stdio Server.
Complies with Anthropic MCP Protocol Specification (2024-11-05).
Supports dual framing (Content-Length header & line-delimited JSON-RPC 2.0).
Zero-Dependency, pure Python Standard Library implementation.
"""
from __future__ import annotations
import sys
import os
import io
import json
import logging
import threading
from typing import Any, Dict, Optional

from src.mcp.tools import MCP_TOOLS_MANIFEST, TOOL_HANDLERS
from src.mcp.security import get_active_workspace_dir
from src.services.metadata_index import MetadataIndex

# Max allowable content length payload (50 MB) to prevent denial-of-service via huge headers
MAX_CONTENT_LENGTH = 50 * 1024 * 1024

# ── Logger Setup (Redirect all internal logs strictly to stderr) ──────────────
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[DocConvert-MCP %(levelname)s] %(asctime)s - %(message)s"
)
logger = logging.getLogger("mcp_server")


class MCPServer:
    """Standard IO Model Context Protocol Server."""

    def __init__(self, stdin_stream=None, stdout_stream=None, index: Optional[MetadataIndex] = None):
        self.stdin = stdin_stream or sys.stdin
        self.stdout = stdout_stream or sys.__stdout__
        self.index = index or MetadataIndex.get_instance()
        self._running = False
        self._write_lock = threading.Lock()

    def send_response(self, response: Dict[str, Any]) -> None:
        """Sends a JSON-RPC 2.0 response object to stdout."""
        payload = json.dumps(response, ensure_ascii=False)
        with self._write_lock:
            try:
                self.stdout.write(payload + "\n")
                self.stdout.flush()
            except (BrokenPipeError, IOError):
                self._running = False

    def send_error(self, req_id: Any, code: int, message: str, data: Any = None) -> None:
        """Sends a standard JSON-RPC error response."""
        err_obj: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            err_obj["data"] = data
        self.send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": err_obj
        })

    def send_result(self, req_id: Any, result: Any) -> None:
        """Sends a standard JSON-RPC success response."""
        self.send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        })

    def handle_initialize(self, req_id: Any, params: Dict[str, Any]) -> None:
        """Handles MCP protocol initialization handshake."""
        logger.info("Initializing MCP connection with client: %s", params.get("clientInfo"))
        self.send_result(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {
                    "listChanged": False
                }
            },
            "serverInfo": {
                "name": "docconvert",
                "version": "1.11.0"
            }
        })

    def handle_tools_list(self, req_id: Any, params: Dict[str, Any]) -> None:
        """Returns the list of available MCP tools and their schemas."""
        self.send_result(req_id, {
            "tools": MCP_TOOLS_MANIFEST
        })

    def handle_tools_call(self, req_id: Any, params: Dict[str, Any]) -> None:
        """Dispatches a tool call request to its corresponding handler."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name or tool_name not in TOOL_HANDLERS:
            self.send_error(req_id, -32601, f"Tool not found: '{tool_name}'")
            return

        handler = TOOL_HANDLERS[tool_name]
        try:
            logger.info("Executing tool '%s' with args: %s", tool_name, list(arguments.keys()))
            tool_output = handler(**arguments, index=self.index)
            is_error = isinstance(tool_output, dict) and "error" in tool_output

            # Format in MCP standard tool result content
            self.send_result(req_id, {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(tool_output, ensure_ascii=False, indent=2)
                    }
                ],
                "isError": is_error
            })
        except TypeError as te:
            logger.error("Invalid arguments for tool %s: %s", tool_name, str(te))
            self.send_error(req_id, -32602, f"Invalid tool arguments: {str(te)}")
        except Exception as e:
            logger.exception("Internal error in tool %s", tool_name)
            self.send_error(req_id, -32603, f"Internal tool execution error: {str(e)}")

    def handle_request(self, request: Dict[str, Any]) -> None:
        """Processes a single parsed JSON-RPC request/notification."""
        if not isinstance(request, dict):
            self.send_error(None, -32600, "Invalid Request: root must be a JSON object")
            return

        method = request.get("method")
        req_id = request.get("id")
        params = request.get("params", {})

        # Handle notifications (requests without an 'id')
        if req_id is None:
            if method == "notifications/initialized":
                logger.info("Client handshake completed (notifications/initialized received)")
            elif method == "notifications/cancelled":
                logger.info("Client requested cancellation of task")
            return

        # Handle standard RPC calls
        if method == "initialize":
            self.handle_initialize(req_id, params)
        elif method == "ping":
            self.send_result(req_id, {})
        elif method == "tools/list":
            self.handle_tools_list(req_id, params)
        elif method == "tools/call":
            self.handle_tools_call(req_id, params)
        else:
            self.send_error(req_id, -32601, f"Method not found: '{method}'")

    def _read_next_message(self) -> Optional[Dict[str, Any]]:
        """
        Reads next message from stdin iteratively without recursion.
        Supports Content-Length framing and line-delimited JSON framing safely.
        """
        while True:
            line = self.stdin.readline()
            if not line:
                return None  # EOF or pipe closed

            # 1. Content-Length header framing
            if line.lower().startswith("content-length:"):
                try:
                    content_len = int(line.split(":", 1)[1].strip())
                    if content_len < 0 or content_len > MAX_CONTENT_LENGTH:
                        logger.error("Content-Length out of bounds: %d bytes", content_len)
                        self.send_error(None, -32700, f"Parse error: Content-Length out of bounds ({content_len})")
                        continue

                    # Consume subsequent header lines until empty line
                    while True:
                        hdr = self.stdin.readline()
                        if hdr in ("\r\n", "\n", ""):
                            break
                    # Read content payload
                    payload = self.stdin.read(content_len)
                    return json.loads(payload)
                except Exception as e:
                    logger.error("Failed to parse Content-Length frame: %s", str(e))
                    self.send_error(None, -32700, f"Parse error in Content-Length frame: {str(e)}")
                    continue

            # 2. Pure line-delimited JSON framing
            stripped = line.strip()
            if not stripped:
                continue

            try:
                return json.loads(stripped)
            except json.JSONDecodeError as jde:
                logger.error("JSON decode error on line: %s | Error: %s", stripped[:100], str(jde))
                self.send_error(None, -32700, f"Parse error: {str(jde)}")
                continue

    def run_forever(self) -> None:
        """Main event loop processing incoming JSON-RPC requests."""
        self._running = True
        logger.info("DocConvert MCP Server started and listening on stdio...")

        while self._running:
            try:
                message = self._read_next_message()
                if message is None:
                    # End of file or pipe closed
                    break
                self.handle_request(message)
            except (KeyboardInterrupt, SystemExit):
                break
            except Exception as e:
                logger.exception("Unexpected error in MCP event loop: %s", str(e))

        logger.info("DocConvert MCP Server stopped.")


def _trigger_background_workspace_sync(index: MetadataIndex) -> None:
    """Attempts to auto-sync the active workspace folder on background thread."""
    def _sync_worker():
        try:
            workspace_dir = get_active_workspace_dir()
            if workspace_dir:
                logger.info("Auto-syncing workspace in background: %s", workspace_dir)
                index.sync_workspace_incremental(workspace_dir)
                logger.info("Workspace background auto-sync completed.")
        except Exception as e:
            logger.warning("Background workspace sync skipped or failed: %s", str(e))

    sync_thread = threading.Thread(target=_sync_worker, name="mcp_bg_sync", daemon=True)
    sync_thread.start()


def ensure_windows_stdio() -> None:
    """
    Recovers standard console handles on Windows when executed from a windowed binary (console=False).
    Attaches to parent process (e.g. Claude Desktop or IDE) console if stdin/stdout are None.
    """
    if sys.platform == "win32":
        if sys.stdin is None or sys.stdout is None or sys.stderr is None:
            try:
                import ctypes
                ATTACH_PARENT_PROCESS = -1
                if ctypes.windll.kernel32.AttachConsole(ATTACH_PARENT_PROCESS):
                    if sys.stdin is None:
                        sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
                    if sys.stdout is None:
                        sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")
                    if sys.stderr is None:
                        sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")
            except Exception:
                pass


def main():
    """CLI Entrypoint for DocConvert MCP Server."""
    ensure_windows_stdio()

    # 1. Protect stdout: redirect standard sys.stdout to sys.stderr
    real_stdout = sys.__stdout__ or sys.stdout
    sys.stdout = sys.stderr

    # 2. Initialize index and trigger background sync
    index = MetadataIndex.get_instance()
    _trigger_background_workspace_sync(index)

    # 3. Start server
    server = MCPServer(stdin_stream=sys.stdin, stdout_stream=real_stdout, index=index)
    server.run_forever()


if __name__ == "__main__":
    main()


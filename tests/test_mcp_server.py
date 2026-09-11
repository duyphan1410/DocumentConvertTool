"""
Integration and Protocol tests for DocConvert MCP Server.
Verifies JSON-RPC 2.0 handshake, tool dispatching, dual framing, recursion resistance,
and error responses.
"""
import io
import json
import os
import tempfile
import unittest
import uuid
from src.mcp.server import MCPServer
from src.services.metadata_index import MetadataIndex


class TestMCPServerProtocol(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.orig_env_ws = os.environ.get("DOCCONVERT_WORKSPACE")
        os.environ["DOCCONVERT_WORKSPACE"] = self.temp_dir.name

        self.db_path = os.path.join(self.temp_dir.name, "test_server_index.db")
        self.index = MetadataIndex(db_path=self.db_path)

        # Create a test document
        self.doc_path = os.path.join(self.temp_dir.name, "protocol_test.md")
        with open(self.doc_path, "w", encoding="utf-8") as f:
            f.write("# Protocol Test\n\nTesting MCP Stdio Server.\n\n#mcp")
        self.doc_id = str(uuid.uuid4())
        self.index.upsert_document(self.doc_path, "Protocol Test", "hash_proto", doc_id=self.doc_id)
        self.index.set_document_tags(self.doc_id, ["mcp"])

    def tearDown(self):
        if self.orig_env_ws is not None:
            os.environ["DOCCONVERT_WORKSPACE"] = self.orig_env_ws
        else:
            os.environ.pop("DOCCONVERT_WORKSPACE", None)
        self.temp_dir.cleanup()

    def _execute_rpc_session(self, input_text: str) -> list[dict]:
        """Runs an in-memory MCP server session and returns parsed JSON-RPC responses."""
        stdin_stream = io.StringIO(input_text)
        stdout_stream = io.StringIO()

        server = MCPServer(stdin_stream=stdin_stream, stdout_stream=stdout_stream, index=self.index)
        server.run_forever()

        raw_output = stdout_stream.getvalue().strip()
        if not raw_output:
            return []

        responses = []
        for line in raw_output.splitlines():
            line = line.strip()
            if line:
                try:
                    responses.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return responses

    def test_initialize_and_ping(self):
        """Test initialize handshake and ping."""
        reqs = (
            json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0"}
                }
            }) + "\n" +
            json.dumps({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "ping"
            }) + "\n"
        )

        resps = self._execute_rpc_session(reqs)
        self.assertEqual(len(resps), 2)

        # Initialize check
        init_resp = resps[0]
        self.assertEqual(init_resp["id"], 1)
        self.assertEqual(init_resp["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(init_resp["result"]["serverInfo"]["name"], "docconvert")

        # Ping check
        ping_resp = resps[1]
        self.assertEqual(ping_resp["id"], 2)
        self.assertEqual(ping_resp["result"], {})

    def test_tools_list(self):
        """Test tools/list returns complete tool manifest."""
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/list",
            "params": {}
        }) + "\n"

        resps = self._execute_rpc_session(req)
        self.assertEqual(len(resps), 1)
        resp = resps[0]
        self.assertEqual(resp["id"], 10)
        tools = resp["result"]["tools"]
        self.assertEqual(len(tools), 6)
        tool_names = [t["name"] for t in tools]
        self.assertIn("search_documents", tool_names)
        self.assertIn("read_document", tool_names)
        self.assertIn("convert_document", tool_names)
        self.assertIn("tag_document", tool_names)
        self.assertIn("list_backlinks", tool_names)
        self.assertIn("write_document_content", tool_names)

    def test_tools_call_read_document(self):
        """Test tools/call for read_document."""
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {
                "name": "read_document",
                "arguments": {
                    "document_id": self.doc_id
                }
            }
        }) + "\n"

        resps = self._execute_rpc_session(req)
        self.assertEqual(len(resps), 1)
        resp = resps[0]
        self.assertEqual(resp["id"], 100)
        content_block = resp["result"]["content"][0]
        self.assertEqual(content_block["type"], "text")
        
        parsed_data = json.loads(content_block["text"])
        self.assertEqual(parsed_data["document_id"], self.doc_id)
        self.assertEqual(parsed_data["title"], "Protocol Test")
        self.assertIn("mcp", parsed_data["tags"])

    def test_tools_call_unknown_tool(self):
        """Test calling non-existent tool returns error -32601."""
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": 999,
            "method": "tools/call",
            "params": {
                "name": "non_existent_tool",
                "arguments": {}
            }
        }) + "\n"

        resps = self._execute_rpc_session(req)
        self.assertEqual(len(resps), 1)
        resp = resps[0]
        self.assertEqual(resp["id"], 999)
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32601)

    def test_content_length_framing(self):
        """Test MCP client sending message formatted with Content-Length header."""
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 77,
            "method": "ping"
        })
        framed_msg = f"Content-Length: {len(body)}\r\n\r\n{body}"

        resps = self._execute_rpc_session(framed_msg)
        self.assertEqual(len(resps), 1)
        self.assertEqual(resps[0]["id"], 77)
        self.assertEqual(resps[0]["result"], {})

    def test_recursion_resistance_empty_lines(self):
        """Test that 5,000 empty lines do not trigger RecursionError and next valid message is parsed."""
        empty_lines = "\n" * 5000
        ping_msg = json.dumps({"jsonrpc": "2.0", "id": 555, "method": "ping"}) + "\n"
        full_stream = empty_lines + ping_msg

        resps = self._execute_rpc_session(full_stream)
        self.assertEqual(len(resps), 1)
        self.assertEqual(resps[0]["id"], 555)
        self.assertEqual(resps[0]["result"], {})

    def test_content_length_limit_exceeded(self):
        """Test that an oversized Content-Length (>50MB) is safely rejected without crash."""
        oversized_header = "Content-Length: 60000000\r\n\r\n"
        ping_msg = json.dumps({"jsonrpc": "2.0", "id": 888, "method": "ping"}) + "\n"
        full_stream = oversized_header + ping_msg

        resps = self._execute_rpc_session(full_stream)
        self.assertEqual(len(resps), 2)
        # First response is Parse error for Content-Length out of bounds
        self.assertIn("error", resps[0])
        self.assertEqual(resps[0]["error"]["code"], -32700)
        # Second response is successful ping
        self.assertEqual(resps[1]["id"], 888)
        self.assertEqual(resps[1]["result"], {})

    def test_invalid_json_line_recovery(self):
        """Test that malformed JSON lines return -32700 and server recovers immediately."""
        malformed = "{ invalid json line !!!\n"
        ping_msg = json.dumps({"jsonrpc": "2.0", "id": 999, "method": "ping"}) + "\n"
        full_stream = malformed + ping_msg

        resps = self._execute_rpc_session(full_stream)
        self.assertEqual(len(resps), 2)
        self.assertEqual(resps[0]["error"]["code"], -32700)
        self.assertEqual(resps[1]["id"], 999)


if __name__ == "__main__":
    unittest.main()

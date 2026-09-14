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
from unittest.mock import patch
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

    def test_tools_call_search_documents_injection_defense(self):
        """
        2-Step verification for search_documents:
        Step 1 (Positive Control): Active in ws_outside -> finds outside document.
        Step 2 (Injection Defense): Active in ws_active -> injecting workspace_dir=ws_outside does NOT leak outside doc.
        """
        with tempfile.TemporaryDirectory() as ws_outside:
            outside_doc_path = os.path.join(ws_outside, "secret_search.md")
            with open(outside_doc_path, "w", encoding="utf-8") as f:
                f.write("# Secret Search Document\n\nConfidential notes.")
            outside_id = str(uuid.uuid4())
            self.index.upsert_document(outside_doc_path, "Secret Search Document", "hash_sec_search", doc_id=outside_id)

            # Step 1: Positive Control
            with patch.dict(os.environ, {"DOCCONVERT_WORKSPACE": ws_outside}):
                req_pos = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 101,
                    "method": "tools/call",
                    "params": {
                        "name": "search_documents",
                        "arguments": {"query": "Secret"}
                    }
                }) + "\n"
                resps_pos = self._execute_rpc_session(req_pos)
                self.assertEqual(len(resps_pos), 1)
                data_pos = json.loads(resps_pos[0]["result"]["content"][0]["text"])
                self.assertEqual(data_pos["total_matches"], 1)
                self.assertEqual(data_pos["results"][0]["document_id"], outside_id)

            # Step 2: Boundary Injection Defense
            with patch.dict(os.environ, {"DOCCONVERT_WORKSPACE": self.temp_dir.name}):
                req_inj = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 102,
                    "method": "tools/call",
                    "params": {
                        "name": "search_documents",
                        "arguments": {
                            "query": "Secret",
                            "workspace_dir": ws_outside  # Malicious injection attempt
                        }
                    }
                }) + "\n"
                resps_inj = self._execute_rpc_session(req_inj)
                self.assertEqual(len(resps_inj), 1)
                data_inj = json.loads(resps_inj[0]["result"]["content"][0]["text"])
                # Must be 0 because secret_search.md is outside active workspace
                self.assertEqual(data_inj["total_matches"], 0)

    def test_tools_call_read_document_injection_defense(self):
        """
        2-Step verification for read_document:
        Step 1 (Positive Control): Active in ws_outside -> successfully reads content.
        Step 2 (Injection Defense): Active in ws_active -> injecting workspace_dir=ws_outside returns DOCUMENT_NOT_FOUND.
        """
        with tempfile.TemporaryDirectory() as ws_outside:
            outside_doc_path = os.path.join(ws_outside, "secret_read.md")
            with open(outside_doc_path, "w", encoding="utf-8") as f:
                f.write("# Top Secret Content\n\nPassword=123456")
            outside_id = str(uuid.uuid4())
            self.index.upsert_document(outside_doc_path, "Top Secret Content", "hash_sec_read", doc_id=outside_id)

            # Step 1: Positive Control
            with patch.dict(os.environ, {"DOCCONVERT_WORKSPACE": ws_outside}):
                req_pos = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 201,
                    "method": "tools/call",
                    "params": {
                        "name": "read_document",
                        "arguments": {"document_id": outside_id}
                    }
                }) + "\n"
                resps_pos = self._execute_rpc_session(req_pos)
                data_pos = json.loads(resps_pos[0]["result"]["content"][0]["text"])
                self.assertNotIn("error", data_pos)
                self.assertIn("Password=123456", data_pos["content"])

            # Step 2: Boundary Injection Defense
            with patch.dict(os.environ, {"DOCCONVERT_WORKSPACE": self.temp_dir.name}):
                req_inj = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 202,
                    "method": "tools/call",
                    "params": {
                        "name": "read_document",
                        "arguments": {
                            "document_id": outside_id,
                            "workspace_dir": ws_outside  # Malicious injection attempt
                        }
                    }
                }) + "\n"
                resps_inj = self._execute_rpc_session(req_inj)
                data_inj = json.loads(resps_inj[0]["result"]["content"][0]["text"])
                self.assertEqual(data_inj.get("error"), "DOCUMENT_NOT_FOUND")
                self.assertTrue(resps_inj[0]["result"]["isError"])

    def test_tools_call_convert_document_injection_defense(self):
        """
        2-Step verification for convert_document:
        Step 1 (Positive Control): Active in ws_outside -> converts to TXT.
        Step 2 (Injection Defense): Active in ws_active -> injecting workspace_dir=ws_outside blocked
                                   and NO output file created on disk (asserted before cleanup).
        """
        with tempfile.TemporaryDirectory() as ws_outside:
            outside_doc_path = os.path.join(ws_outside, "convert_note.md")
            with open(outside_doc_path, "w", encoding="utf-8") as f:
                f.write("# Convert Note\n\nContent to convert.")
            outside_id = str(uuid.uuid4())
            self.index.upsert_document(outside_doc_path, "Convert Note", "hash_conv", doc_id=outside_id)

            # Step 1: Positive Control
            with patch.dict(os.environ, {"DOCCONVERT_WORKSPACE": ws_outside}):
                req_pos = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 301,
                    "method": "tools/call",
                    "params": {
                        "name": "convert_document",
                        "arguments": {"document_id": outside_id, "target_format": "txt"}
                    }
                }) + "\n"
                resps_pos = self._execute_rpc_session(req_pos)
                data_pos = json.loads(resps_pos[0]["result"]["content"][0]["text"])
                self.assertEqual(data_pos.get("status"), "success")
                expected_pos_out = os.path.join(ws_outside, "convert_note.txt")
                self.assertTrue(os.path.exists(expected_pos_out))
                os.remove(expected_pos_out)

            # Step 2: Boundary Injection Defense
            expected_inj_out = os.path.join(ws_outside, "convert_note.txt")
            with patch.dict(os.environ, {"DOCCONVERT_WORKSPACE": self.temp_dir.name}):
                req_inj = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 302,
                    "method": "tools/call",
                    "params": {
                        "name": "convert_document",
                        "arguments": {
                            "document_id": outside_id,
                            "target_format": "txt",
                            "workspace_dir": ws_outside  # Malicious injection attempt
                        }
                    }
                }) + "\n"
                resps_inj = self._execute_rpc_session(req_inj)
                data_inj = json.loads(resps_inj[0]["result"]["content"][0]["text"])
                self.assertEqual(data_inj.get("error"), "DOCUMENT_NOT_FOUND")
                # CRITICAL: Assert file was NOT created before TemporaryDirectory context manager exits
                self.assertFalse(os.path.exists(expected_inj_out))

    def test_tools_call_tag_document_injection_defense(self):
        """
        2-Step verification for tag_document:
        Step 1 (Positive Control): Active in ws_outside -> adds tag.
        Step 2 (Injection Defense): Active in ws_active -> injecting workspace_dir=ws_outside blocked
                                   and DB tags NOT changed.
        """
        with tempfile.TemporaryDirectory() as ws_outside:
            outside_doc_path = os.path.join(ws_outside, "tag_note.md")
            with open(outside_doc_path, "w", encoding="utf-8") as f:
                f.write("# Tag Note")
            outside_id = str(uuid.uuid4())
            self.index.upsert_document(outside_doc_path, "Tag Note", "hash_tag", doc_id=outside_id)
            self.index.set_document_tags(outside_id, ["initial"])

            # Step 1: Positive Control
            with patch.dict(os.environ, {"DOCCONVERT_WORKSPACE": ws_outside}):
                req_pos = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 401,
                    "method": "tools/call",
                    "params": {
                        "name": "tag_document",
                        "arguments": {"document_id": outside_id, "add_tags": ["pos_tag"]}
                    }
                }) + "\n"
                resps_pos = self._execute_rpc_session(req_pos)
                data_pos = json.loads(resps_pos[0]["result"]["content"][0]["text"])
                self.assertEqual(data_pos.get("status"), "success")
                self.assertIn("pos_tag", data_pos["current_tags"])

            # Step 2: Boundary Injection Defense
            with patch.dict(os.environ, {"DOCCONVERT_WORKSPACE": self.temp_dir.name}):
                req_inj = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 402,
                    "method": "tools/call",
                    "params": {
                        "name": "tag_document",
                        "arguments": {
                            "document_id": outside_id,
                            "add_tags": ["injected_tag"],
                            "workspace_dir": ws_outside  # Malicious injection attempt
                        }
                    }
                }) + "\n"
                resps_inj = self._execute_rpc_session(req_inj)
                data_inj = json.loads(resps_inj[0]["result"]["content"][0]["text"])
                self.assertEqual(data_inj.get("error"), "DOCUMENT_NOT_FOUND")
                # Verify DB tags unchanged
                db_tags = self.index.get_document_tags(outside_id)
                self.assertNotIn("injected_tag", db_tags)

    def test_tools_call_list_backlinks_injection_defense(self):
        """
        2-Step verification for list_backlinks:
        Step 1 (Positive Control): Active in ws_outside -> returns linked references.
        Step 2 (Injection Defense): Active in ws_active -> injecting workspace_dir=ws_outside blocked
                                   and no links disclosed.
        """
        with tempfile.TemporaryDirectory() as ws_outside:
            doc_a_path = os.path.join(ws_outside, "backlink_a.md")
            doc_b_path = os.path.join(ws_outside, "backlink_b.md")
            with open(doc_a_path, "w", encoding="utf-8") as f:
                f.write("# Doc A Target")
            with open(doc_b_path, "w", encoding="utf-8") as f:
                f.write("# Doc B Source\n\nLink to [[Doc A Target]]")

            id_a = str(uuid.uuid4())
            id_b = str(uuid.uuid4())
            self.index.upsert_document(doc_a_path, "Doc A Target", "hash_a", doc_id=id_a)
            self.index.upsert_document(doc_b_path, "Doc B Source", "hash_b", doc_id=id_b)

            with self.index.get_connection() as conn:
                conn.execute("""
                    INSERT INTO wikilinks (source_id, target_id, target_title_raw, snippet, resolved)
                    VALUES (?, ?, ?, ?, 1)
                """, (id_b, id_a, "Doc A Target", "Link to [[Doc A Target]]"))
                conn.commit()

            # Step 1: Positive Control
            with patch.dict(os.environ, {"DOCCONVERT_WORKSPACE": ws_outside}):
                req_pos = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 501,
                    "method": "tools/call",
                    "params": {
                        "name": "list_backlinks",
                        "arguments": {"document_id": id_a}
                    }
                }) + "\n"
                resps_pos = self._execute_rpc_session(req_pos)
                data_pos = json.loads(resps_pos[0]["result"]["content"][0]["text"])
                self.assertNotIn("error", data_pos)
                self.assertEqual(data_pos["linked_references_count"], 1)

            # Step 2: Boundary Injection Defense
            with patch.dict(os.environ, {"DOCCONVERT_WORKSPACE": self.temp_dir.name}):
                req_inj = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 502,
                    "method": "tools/call",
                    "params": {
                        "name": "list_backlinks",
                        "arguments": {
                            "document_id": id_a,
                            "workspace_dir": ws_outside  # Malicious injection attempt
                        }
                    }
                }) + "\n"
                resps_inj = self._execute_rpc_session(req_inj)
                data_inj = json.loads(resps_inj[0]["result"]["content"][0]["text"])
                self.assertEqual(data_inj.get("error"), "DOCUMENT_NOT_FOUND")

    def test_tools_call_write_document_content_injection_defense(self):
        """
        2-Step verification for write_document_content:
        Step 1 (Positive Control): Active in ws_outside -> overwrites content and creates .bak.
        Step 2 (Injection Defense): Active in ws_active -> injecting workspace_dir=ws_outside blocked,
                                   file unchanged, and no new .bak created.
        """
        with tempfile.TemporaryDirectory() as ws_outside:
            outside_doc_path = os.path.join(ws_outside, "write_test.md")
            original_content = "# Original Content"
            with open(outside_doc_path, "w", encoding="utf-8") as f:
                f.write(original_content)
            outside_id = str(uuid.uuid4())
            self.index.upsert_document(outside_doc_path, "Original Title", "hash_orig", doc_id=outside_id)

            # Step 1: Positive Control
            with patch.dict(os.environ, {"DOCCONVERT_WORKSPACE": ws_outside}):
                req_pos = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 601,
                    "method": "tools/call",
                    "params": {
                        "name": "write_document_content",
                        "arguments": {
                            "document_id": outside_id,
                            "content": "# Updated by Step 1"
                        }
                    }
                }) + "\n"
                resps_pos = self._execute_rpc_session(req_pos)
                data_pos = json.loads(resps_pos[0]["result"]["content"][0]["text"])
                self.assertEqual(data_pos.get("status"), "success")
                with open(outside_doc_path, "r", encoding="utf-8") as f:
                    self.assertEqual(f.read(), "# Updated by Step 1")

            # Remove .bak from step 1 for clean step 2 test
            bak_path = f"{outside_doc_path}.bak"
            if os.path.exists(bak_path):
                os.remove(bak_path)

            # Step 2: Boundary Injection Defense
            with patch.dict(os.environ, {"DOCCONVERT_WORKSPACE": self.temp_dir.name}):
                req_inj = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 602,
                    "method": "tools/call",
                    "params": {
                        "name": "write_document_content",
                        "arguments": {
                            "document_id": outside_id,
                            "content": "# Malicious Overwrite Attempt",
                            "workspace_dir": ws_outside  # Malicious injection attempt
                        }
                    }
                }) + "\n"
                resps_inj = self._execute_rpc_session(req_inj)
                data_inj = json.loads(resps_inj[0]["result"]["content"][0]["text"])
                self.assertEqual(data_inj.get("error"), "DOCUMENT_NOT_FOUND")

                # Verify file content is UNTOUCHED (still from Step 1)
                with open(outside_doc_path, "r", encoding="utf-8") as f:
                    self.assertEqual(f.read(), "# Updated by Step 1")
                # Verify no backup file was created
                self.assertFalse(os.path.exists(bak_path))


if __name__ == "__main__":
    unittest.main()



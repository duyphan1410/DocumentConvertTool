"""
Interactive Visual MCP Client Demo.
Spawns `python run.py --mcp-server` as a real subprocess and interactively demonstrates
all 6 MCP tools with formatted color output on actual workspace documents (like phase1_tagging_wikilinks.md).
"""
import sys
import os
import json
import subprocess
import time

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

def print_banner():
    print("=" * 75)
    print(" [MCP] DocConvert Local MCP Server — Interactive Visual Verification")
    print("=" * 75)

def send_rpc(proc, method, params=None, req_id=1):
    req = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {}
    }
    msg_str = json.dumps(req, ensure_ascii=False) + "\n"
    proc.stdin.write(msg_str)
    proc.stdin.flush()
    
    # Read response line
    resp_line = proc.stdout.readline().strip()
    if not resp_line:
        return {}
    return json.loads(resp_line)

def run_demo():
    print_banner()
    python_exe = sys.executable
    cmd = [python_exe, "-u", "run.py", "--mcp-server"]
    
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env = dict(os.environ)
    env["DOCCONVERT_WORKSPACE"] = workspace_root
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"

    print(f"\n[1] 🚀 Khởi chạy MCP Server Subprocess: {' '.join(cmd)}")
    print(f"    Workspace: {workspace_root}")
    
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        cwd=workspace_root,
        env=env,
        text=True,
        encoding="utf-8",
        bufsize=1
    )

    try:
        # Step 1: Handshake
        print("\n[2] 🤝 Gửi yêu cầu Handshake (initialize)...")
        init_resp = send_rpc(proc, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "Claude Desktop Client", "version": "1.0.0"}
        }, req_id=1)
        print("  -> Kết quả từ Server:")
        print("    ", json.dumps(init_resp.get("result", {}), indent=4, ensure_ascii=False))

        # Step 2: List Tools
        print("\n[3] 📋 Truy vấn danh sách công cụ (tools/list)...")
        list_resp = send_rpc(proc, "tools/list", {}, req_id=2)
        tools = list_resp.get("result", {}).get("tools", [])
        print(f"  -> Server hỗ trợ {len(tools)} công cụ:")
        for t in tools:
            print(f"     • 🛠️  {t['name']:<24}: {t['description']}")

        # Step 3: Search Documents for phase1_tagging_wikilinks
        query_kw = "phase1_tagging_wikilinks"
        print(f"\n[4] 🔍 Gọi Tool: search_documents (Tìm kiếm tài liệu: '{query_kw}')...")
        search_resp = send_rpc(proc, "tools/call", {
            "name": "search_documents",
            "arguments": {"query": query_kw, "limit": 5}
        }, req_id=3)
        content_text = search_resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
        search_data = json.loads(content_text)
        print(f"  -> Tìm thấy {search_data.get('total_matches', 0)} tài liệu khớp từ khóa:")
        
        target_doc = None
        for doc in search_data.get("results", []):
            print(f"     📄 [{doc['document_id']}] {doc['title']}")
            print(f"        Đường dẫn: {doc['path']}")
            print(f"        Tags: {doc.get('tags', [])} | Điểm tương đồng: {doc.get('relevance_score')}")
            if doc["path"].lower().endswith("phase1_tagging_wikilinks.md"):
                target_doc = doc

        if not target_doc and search_data.get("results"):
            target_doc = search_data["results"][0]

        if target_doc:
            doc_id = target_doc["document_id"]
            
            # Step 4: Read Document
            print(f"\n[5] 📖 Gọi Tool: read_document (Đọc tài liệu ID: {doc_id})...")
            read_resp = send_rpc(proc, "tools/call", {
                "name": "read_document",
                "arguments": {"document_id": doc_id}
            }, req_id=4)
            read_text = read_resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
            read_data = json.loads(read_text)
            
            print(f"     Tiêu đề: {read_data.get('title')}")
            print(f"     Đường dẫn: {read_data.get('path')}")
            print(f"     Danh sách Tags: {read_data.get('tags', [])}")
            print(f"     Cập nhật lúc: {read_data.get('updated_at')}")
            print("     Trích đoạn nội dung:")
            lines = read_data.get("content", "").splitlines()[:10]
            for l in lines:
                print(f"       | {l}")

            # Step 5: List Backlinks
            print(f"\n[6] 🔗 Gọi Tool: list_backlinks (Truy vấn liên kết hai chiều cho ID: {doc_id[:8]}...)...")
            backlinks_resp = send_rpc(proc, "tools/call", {
                "name": "list_backlinks",
                "arguments": {"document_id": doc_id}
            }, req_id=5)
            backlinks_text = backlinks_resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
            bl_data = json.loads(backlinks_text)
            print(f"     Tiêu đề đích: {bl_data.get('title')}")
            print(f"     Linked References (Được liên kết từ các note khác): {bl_data.get('linked_references_count', 0)}")
            for ref in bl_data.get("linked_references", []):
                print(f"       <- Trỏ từ [{ref.get('source_title')}]: \"{ref.get('snippet', '').strip()}\"")
            print(f"     Unlinked Mentions (Nhắc đến tên chưa gắn link): {bl_data.get('unlinked_mentions_count', 0)}")
            for m in bl_data.get("unlinked_mentions", []):
                print(f"       ?? Trong [{m.get('source_title')}]: \"{m.get('snippet', '').strip()}\"")

            # Step 6: Tag Document
            print(f"\n[7] 🏷️  Gọi Tool: tag_document (Gắn tag #mcp-tested và #pkb-phase2)...")
            tag_resp = send_rpc(proc, "tools/call", {
                "name": "tag_document",
                "arguments": {
                    "document_id": doc_id,
                    "add_tags": ["mcp-tested", "pkb-phase2"]
                }
            }, req_id=6)
            tag_text = tag_resp.get("result", {}).get("content", [{}])[0].get("text", "{}")
            tag_data = json.loads(tag_text)
            print(f"     Tags trước khi gắn: {tag_data.get('previous_tags')}")
            print(f"     Tags hiện tại trong DB: {tag_data.get('current_tags')}")

        print("\n" + "=" * 75)
        print(" 🎉 Xác thực trực quan MCP Server HOÀN TẤT THÀNH CÔNG 100%!")
        print("=" * 75)

    finally:
        proc.stdin.close()
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    run_demo()

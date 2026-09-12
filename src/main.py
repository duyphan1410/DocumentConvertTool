import sys


def main():
    # 1. Headless Subprocess: YouTube Background Audio Player
    if "--youtube-player" in sys.argv:
        from src.services.youtube_player import _run_player_subprocess
        _run_player_subprocess()
        return

    # 2. Headless Subprocess: Local MCP Stdio Server for Claude Desktop & IDEs
    if "--mcp-server" in sys.argv:
        from src.mcp.server import ensure_windows_stdio, MCPServer, _trigger_background_workspace_sync
        ensure_windows_stdio()

        # Immediately isolate stdout to stderr before importing any modules
        real_stdout = sys.__stdout__ or sys.stdout
        sys.stdout = sys.stderr

        from src.services.metadata_index import MetadataIndex

        index = MetadataIndex.get_instance()
        _trigger_background_workspace_sync(index)
        server = MCPServer(stdin_stream=sys.stdin, stdout_stream=real_stdout, index=index)
        server.run_forever()
        return

    # 3. GUI Desktop Mode: Lazy load Flet framework and UI components
    import flet as ft
    from src.ui_flet.app import main as flet_main
    ft.app(target=flet_main)


if __name__ == "__main__":
    main()

import sys


def main():
    # 1. Headless Subprocess: YouTube Background Audio Player
    if "--youtube-player" in sys.argv:
        from src.services.youtube_player import _run_player_subprocess
        _run_player_subprocess()
        return

    # 2. Headless Subprocess: Local MCP Stdio Server for Claude Desktop & IDEs
    if "--mcp-server" in sys.argv:
        from src.mcp.server import main as run_mcp_server
        run_mcp_server()
        return

    # 3. GUI Desktop Mode: Lazy load Flet framework and UI components
    import flet as ft
    from src.ui_flet.app import main as flet_main
    ft.app(target=flet_main)


if __name__ == "__main__":
    main()

import sys
import flet as ft
from src.ui_flet.app import main as flet_main


def main():
    if "--youtube-player" in sys.argv:
        from src.services.youtube_player import _run_player_subprocess
        _run_player_subprocess()
        return
    ft.app(target=flet_main)


if __name__ == "__main__":
    main()


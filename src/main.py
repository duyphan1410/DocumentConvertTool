import os
import flet as ft
from src.ui_flet.app import main as flet_main

def main():
    assets_dir = os.path.abspath("assets")
    ft.run(flet_main, assets_dir=assets_dir)

if __name__ == "__main__":
    main()

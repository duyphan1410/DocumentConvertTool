#!/usr/bin/env python
"""
Launcher script for the Document Converter Workspace.
Run this script to start the application.
"""

import sys
from src.main import main

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--youtube-player":
        from src.services.youtube_player import _run_player_subprocess
        _run_player_subprocess()
    else:
        main()

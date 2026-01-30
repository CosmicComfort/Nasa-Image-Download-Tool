"""
Entry point for running NASA Media Downloader as a module.

Usage:
    python -m nasa_downloader [OPTIONS]
    python -m nasa_downloader interactive
    python -m nasa_downloader download --query "mars" --limit 5
"""

from .cli.app import main

if __name__ == "__main__":
    main()

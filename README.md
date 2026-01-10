# NASA Image Download Tool

A small, safe, cross-platform tool to search the NASA Images API and download image assets and metadata.

Features

* Search the NASA Images API (https://images-api.nasa.gov).
* Download image assets with selectable quality (small, medium, large, orig, or all).
* Save metadata as both JSON and readable TXT.
* Safe directory creation with fallbacks for non-writable locations.
* Retries and progress bars for downloads.
* CLI with optional interactive prompts.

Usage (interactive)

* NASA-DownloadTool\NASA_DownloadToolV13.py

  * Follow prompts for query, output folder, what to download, quality, and limits.

Usage (CLI)

* python nasa\_downloader.py --query "mars" --output ./nasabackup --qualities orig --limit 25

Requirements

* Make sure you have the latest Python installed https://www.python.org/
* open cmd in same path as /requirements.txt
* pip -r install requirements.txt



Notes

* The tool uses the public NASA Images API and does not require an API key.
* Downloading "all" qualities will require more storage and time.

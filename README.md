# NASA Image Downloader

A full-featured NASA Images API downloader script.

Features
- Search NASA Images API and download images and/or metadata.
- Concurrent downloads with retries/backoff.
- Hashing (SHA-256) based deduplication using a small SQLite database.
- Save metadata as TXT and/or JSON.
- Rotating logs with stack traces for errors.
- CLI with interactive defaults for easy use.

Requirements
- Python 3.8+
- requests
  - Install with: `pip install requests`

Quick install
1. Save `nasa_downloader.py` somewhere.
2. (Optional) Create a virtualenv:
   - python -m venv venv
   - source venv/bin/activate
   - pip install requests

Basic usage (interactive)
- Run: `python nasa_downloader.py` and follow prompts.

Non-interactive example
```
python nasa_downloader.py \
  --query moon \
  --save-dir ./nasabackup \
  --qualities all \
  --download both \
  --max 200 \
  --rate 0.5 \
  --workers 6 \
  --dedupe \
  --metadata-format both
```

Key options
- --query / -q : search term (interactive default "space").
- --save-dir / -s : output directory (default ./nasabackup).
- --download / -d : "images", "metadata", or "both" (default both).
- --qualities : comma-separated from small,medium,large,orig or "all".
- --rate : seconds delay between search results (default 1.0).
- --max : maximum number of images to process.
- --workers : number of concurrent image download workers (default 4).
- --dedupe : enable deduplication by image hash (recommended).
- --db : custom SQLite DB path for dedupe (default: `<save_dir>/nasa_downloader.db`).
- --metadata-format : `txt`, `json`, or `both`.
- --skip-existing-by-name : skip saving if a file with same name exists and identical.
- --retries / --backoff / --timeout : HTTP retry/backoff/timeouts.
- --user-agent : custom User-Agent string.
- --log-level : console log level (DEBUG/INFO/etc).

Logs
- A rotating log file is created under `<save_dir>/logs/nasa_downloader.log`.

Behavior notes
- Metadata is saved once per item into `<save_dir>/Metadata` as TXT and/or JSON depending on settings.
- Images are saved in per-quality folders (`Low/Images`, `Medium/Images`, `High/Images`, `Original/Images`).
- The script uses the NASA "asset" endpoint to discover available image URLs; if asset lookup fails it falls back to common URL patterns.
- Downloads are atomic: the file is first downloaded to a temp file, hashed, checked for duplicates, then moved to final location.
- Duplicate images (by hash) are not stored twice when `--dedupe` is used; their URLs are still recorded in the DB.

Extending
- To add image hashing algorithm, pass `--hash-algo` (default `sha256`).
- To change DB location, pass `--db`.
- To disable file logging, comment out `configure_file_logging` call in the script (or adjust as needed).

Support / Next steps
- I can add optional concurrency throttling per-host, S3 upload support, image format conversion, or a small UI. Tell me which you'd like next.

License
- Use this script at your own risk. The NASA Images API is public; be courteous (respect rate limits and server load).
- No warranty.

Enjoy!
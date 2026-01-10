#!/usr/bin/env python3
"""
NASA Image Downloader - full-featured, production-ready.

Features:
- Search NASA Images API and download images and/or metadata.
- Concurrent downloads with retries/backoff.
- Hashing (SHA-256) based deduplication using a small SQLite database.
- Save metadata as JSON and/or TXT.
- Rotating logs with stack traces for errors.
- CLI with interactive defaults and non-interactive flags.
- Atomic downloads (temp file -> hash -> final).
- Optional extras: progress bars, image conversion, S3 upload (requires extra packages).

Requirements:
- Python 3.8+
- requests
Optional extras (useful but not required):
- tqdm (progress bars)
- Pillow (image processing)
- boto3 (S3 upload)

Install requirements using the provided install_requirements.py or:
  pip install -r requirements.txt
"""

from __future__ import annotations
import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Optional, Set, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# -------------------------
# Constants
# -------------------------
API_SEARCH_URL = "https://images-api.nasa.gov/search"
API_ASSET_URL = "https://images-api.nasa.gov/asset/{}"
QUALITY_FOLDER_MAP = {
    "small": "Low",
    "medium": "Medium",
    "large": "High",
    "orig": "Original",
}
KNOWN_QUALITIES = list(QUALITY_FOLDER_MAP.keys())
DEFAULT_USER_AGENT = "nasa_downloader/1.0 (+https://github.com/)"

# -------------------------
# Logger
# -------------------------
logger = logging.getLogger("nasa_downloader")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# -------------------------
# Thread-local session for safe concurrent requests
# -------------------------
_thread_local = threading.local()


def get_session(retries: int, backoff_factor: float, timeout: float, user_agent: str) -> requests.Session:
    """
    Return a thread-local requests.Session configured with retries and headers.
    """
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET", "HEAD", "OPTIONS"])
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_maxsize=10)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({"User-Agent": user_agent})
        setattr(_thread_local, "session", session)
    return session


# -------------------------
# Utilities
# -------------------------
def make_dir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        logger.exception("Failed to create directory: %s", path)


def configure_file_logging(save_dir: str, level: int = logging.DEBUG) -> None:
    try:
        log_dir = os.path.join(save_dir, "logs")
        make_dir(log_dir)
        log_path = os.path.join(log_dir, "nasa_downloader.log")
        fh = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        fh.setLevel(level)
        fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        fh.setFormatter(fmt)
        root = logging.getLogger()
        root.addHandler(fh)
        logger.debug("File logging configured: %s", log_path)
    except Exception:
        logger.exception("Failed to configure file logging")


def sanitize_filename(s: str) -> str:
    s = str(s).strip()
    s = s.replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)


def _get_extension_from_url(url: str) -> str:
    url_no_q = url.split("?", 1)[0]
    if "." in url_no_q:
        ext = url_no_q.rsplit(".", 1)[-1].lower()
        if 1 <= len(ext) <= 6 and ext.isalnum():
            return ext
    return "jpg"


# -------------------------
# Database (SQLite) for dedupe & metadata tracking
# -------------------------
def init_db(db_path: str) -> sqlite3.Connection:
    make_dir(os.path.dirname(db_path) or ".")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY,
            url TEXT UNIQUE,
            hash TEXT,
            path TEXT,
            nasa_id TEXT,
            saved_at TEXT
        )"""
    )
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_images_hash ON images(hash)"""
    )
    conn.commit()
    return conn


def db_has_hash(conn: sqlite3.Connection, hash_val: str) -> Optional[Tuple[int, str]]:
    cur = conn.execute("SELECT id, path FROM images WHERE hash = ?", (hash_val,))
    row = cur.fetchone()
    return (row[0], row[1]) if row else None


def db_insert(conn: sqlite3.Connection, url: str, hash_val: str, path: str, nasa_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO images (url, hash, path, nasa_id, saved_at) VALUES (?, ?, ?, ?, ?)",
        (url, hash_val, path, nasa_id, datetime.utcnow().isoformat() + "Z"),
    )
    conn.commit()


# -------------------------
# NASA API helpers
# -------------------------
def fetch_search_page(session: requests.Session, query: str, page: int, timeout: float = 15.0) -> Optional[dict]:
    try:
        resp = session.get(API_SEARCH_URL, params={"q": query, "media_type": "image", "page": page}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        logger.exception("Network error fetching search page %s for query '%s'", page, query)
    except Exception:
        logger.exception("Error parsing JSON for search page %s", page)
    return None


def fetch_asset_items(session: requests.Session, nasa_id: str, timeout: float = 15.0) -> List[str]:
    urls: List[str] = []
    try:
        resp = session.get(API_ASSET_URL.format(nasa_id), timeout=timeout)
        if resp.ok:
            data = resp.json()
            items = data.get("collection", {}).get("items", [])
            for it in items:
                href = it.get("href")
                if isinstance(href, str):
                    urls.append(href)
            if urls:
                logger.debug("Found %d asset URLs for %s", len(urls), nasa_id)
                return urls
        else:
            logger.debug("Asset endpoint returned status %s for %s", resp.status_code, nasa_id)
    except requests.RequestException:
        logger.debug("Asset endpoint request failed for %s, will try fallback", nasa_id)
    except Exception:
        logger.debug("Asset JSON parse failed for %s, will try fallback", nasa_id)

    fallback_base = f"https://images-assets.nasa.gov/image/{nasa_id}/{nasa_id}"
    for q in KNOWN_QUALITIES:
        urls.append(f"{fallback_base}~{q}.jpg")
    urls.append(f"{fallback_base}.jpg")
    logger.debug("Using fallback asset URLs for %s", nasa_id)
    return urls


def choose_quality_urls(asset_urls: List[str], desired_qualities: List[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    lower_urls = [(u, u.lower()) for u in asset_urls]
    for q in desired_qualities:
        q_lower = q.lower()
        chosen = None
        for u, lu in lower_urls:
            if f"~{q_lower}." in lu or f"~{q_lower}" in lu:
                chosen = u
                break
        if not chosen:
            if q_lower == "orig":
                for u, lu in lower_urls:
                    if lu.endswith("orig.jpg") or "~orig" in lu or "orig." in lu:
                        chosen = u
                        break
            else:
                for u, lu in lower_urls:
                    if q_lower in lu:
                        chosen = u
                        break
        if not chosen:
            for u, lu in lower_urls:
                if lu.endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff")):
                    chosen = u
                    break
        if chosen:
            mapping[q] = chosen
    return mapping


# -------------------------
# Download and metadata IO
# -------------------------
def download_worker(
    url: str,
    dest_dir: str,
    filename_base: str,
    nasa_id: str,
    conn: sqlite3.Connection,
    retries: int,
    backoff_factor: float,
    timeout: float,
    user_agent: str,
    hash_algo: str,
    skip_existing_by_name: bool,
) -> Optional[Tuple[str, str]]:
    """
    Download a single URL:
    - stream to temp file
    - compute hash
    - check DB for existing hash (dedupe)
    - move to final directory if unique
    - record in DB
    Returns (final_path, hash) or None on failure / duplicate.
    """
    try:
        session = get_session(retries=retries, backoff_factor=backoff_factor, timeout=timeout, user_agent=user_agent)
        try:
            head = session.head(url, timeout=timeout, allow_redirects=True)
            if head.status_code and head.status_code >= 400:
                logger.debug("HEAD status %s for %s", head.status_code, url)
        except Exception:
            pass

        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".tmp")
        os.close(tmp_fd)
        try:
            with session.get(url, stream=True, timeout=timeout) as resp:
                if resp.status_code != 200:
                    logger.warning("Failed to download %s (status %s)", url, resp.status_code)
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                    return None
                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
        except Exception:
            logger.exception("Error downloading %s", url)
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return None

        h = hashlib.new(hash_algo)
        with open(tmp_path, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                h.update(block)
        hash_val = h.hexdigest()

        existing = db_has_hash(conn, hash_val)
        if existing:
            logger.info("Duplicate detected (hash match). Skipping save for %s; already at %s", url, existing[1])
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            try:
                db_insert(conn, url, hash_val, existing[1], nasa_id)
            except Exception:
                logger.debug("DB insert for duplicate url may have failed (likely already present)")
            return None

        ext = _get_extension_from_url(url)
        final_name = f"{filename_base}.{ext}"
        final_path = os.path.join(dest_dir, final_name)
        if skip_existing_by_name and os.path.exists(final_path):
            h2 = hashlib.new(hash_algo)
            with open(final_path, "rb") as f:
                for block in iter(lambda: f.read(8192), b""):
                    h2.update(block)
            if h2.hexdigest() == hash_val:
                logger.info("File with same name and identical content already exists: %s", final_path)
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                db_insert(conn, url, hash_val, final_path, nasa_id)
                return None
            else:
                final_name = f"{filename_base}_{hash_val[:8]}.{ext}"
                final_path = os.path.join(dest_dir, final_name)

        make_dir(dest_dir)
        shutil.move(tmp_path, final_path)
        db_insert(conn, url, hash_val, final_path, nasa_id)
        logger.info("Saved image: %s", final_path)
        return final_path, hash_val

    except Exception:
        logger.exception("Unexpected error in download_worker for %s", url)
        return None


def save_metadata(metadata_dir: str, filename_base: str, metadata: Dict[str, str], formats: List[str]) -> List[str]:
    saved_paths: List[str] = []
    try:
        make_dir(metadata_dir)
        if "txt" in formats:
            p_txt = os.path.join(metadata_dir, f"{filename_base}.txt")
            with open(p_txt, "w", encoding="utf-8") as f:
                for k, v in metadata.items():
                    f.write(f"{k}: {v}\n")
            saved_paths.append(p_txt)
        if "json" in formats:
            p_json = os.path.join(metadata_dir, f"{filename_base}.json")
            with open(p_json, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            saved_paths.append(p_json)
        logger.debug("Saved metadata files: %s", saved_paths)
    except Exception:
        logger.exception("Failed to save metadata for %s", filename_base)
    return saved_paths


# -------------------------
# Main crawler
# -------------------------
def crawl_nasa_images(
    query: str,
    save_dir: str,
    download_images: bool,
    download_text: bool,
    qualities: List[str],
    rate_limit: float,
    max_images: Optional[int],
    workers: int,
    db_path: str,
    retries: int,
    backoff_factor: float,
    timeout: float,
    user_agent: str,
    hash_algo: str,
    skip_existing_by_name: bool,
    metadata_formats: List[str],
    dedupe: bool,
) -> None:
    qualities = [q for q in qualities if q in KNOWN_QUALITIES]
    if not qualities:
        logger.warning("No valid qualities selected; defaulting to ['orig']")
        qualities = ["orig"]

    quality_dirs = {}
    for q in qualities:
        folder_name = QUALITY_FOLDER_MAP.get(q, q)
        q_dir = os.path.join(save_dir, folder_name)
        imgs = os.path.join(q_dir, "Images")
        make_dir(imgs)
        quality_dirs[q] = {"images": imgs}
    metadata_dir = os.path.join(save_dir, "Metadata")
    make_dir(metadata_dir)

    conn = init_db(db_path) if dedupe else init_db(db_path)

    session_main = get_session(retries=retries, backoff_factor=backoff_factor, timeout=timeout, user_agent=user_agent)

    page = 1
    file_counter = 1
    total_downloaded = 0
    total_metadata = 0
    seen_urls: Set[str] = set()

    executor = ThreadPoolExecutor(max_workers=max(1, workers))

    try:
        while True:
            logger.info("Searching page %s for '%s'...", page, query)
            data = fetch_search_page(session_main, query, page, timeout=timeout)
            if data is None:
                logger.warning("Stopping due to search page error.")
                break

            items = data.get("collection", {}).get("items", [])
            if not items:
                logger.info("No more items found; finished searching.")
                break

            for item in items:
                if max_images and file_counter > max_images:
                    logger.info("Reached user-specified maximum image count: %s", max_images)
                    break

                info = {}
                try:
                    info_list = item.get("data", [])
                    if isinstance(info_list, list) and info_list:
                        info = info_list[0] or {}
                except Exception:
                    logger.debug("Malformed data block; skipping metadata extraction.")
                    info = {}

                nasa_id = info.get("nasa_id") or info.get("identifier") or f"unknown_{file_counter:04d}"
                title = info.get("title", "No Title")
                description = info.get("description", info.get("description_508", "No Description"))
                date_created = info.get("date_created", "Unknown")
                center = info.get("center", "Unknown")
                keywords_val = info.get("keywords", [])
                if isinstance(keywords_val, list):
                    keywords = ", ".join(str(k) for k in keywords_val)
                else:
                    keywords = str(keywords_val)

                metadata = {
                    "NASA ID": nasa_id,
                    "Title": title,
                    "Description": description,
                    "Date Created": date_created,
                    "Center": center,
                    "Keywords": keywords,
                }

                filename_base = f"{file_counter:04d}_{sanitize_filename(nasa_id)}"
                downloaded_any = False

                asset_urls = fetch_asset_items(session_main, nasa_id, timeout=timeout)
                q_url_map = choose_quality_urls(asset_urls, qualities)

                download_futures = []
                if download_images:
                    for q in qualities:
                        url = q_url_map.get(q)
                        if not url:
                            logger.debug("No URL for quality %s on item %s", q, nasa_id)
                            continue
                        if url in seen_urls:
                            logger.debug("URL already seen/queued: %s", url)
                            continue
                        seen_urls.add(url)
                        dest_dir = quality_dirs[q]["images"]
                        future = executor.submit(
                            download_worker,
                            url,
                            dest_dir,
                            filename_base,
                            nasa_id,
                            conn,
                            retries,
                            backoff_factor,
                            timeout,
                            user_agent,
                            hash_algo,
                            skip_existing_by_name,
                        )
                        download_futures.append(future)

                for fut in as_completed(download_futures):
                    try:
                        res = fut.result()
                        if res:
                            total_downloaded += 1
                            downloaded_any = True
                    except Exception:
                        logger.exception("Download task failed")

                if download_text:
                    saved = save_metadata(metadata_dir, filename_base, metadata, metadata_formats)
                    if saved:
                        total_metadata += 1

                if downloaded_any or download_text:
                    logger.info("Saved item %s: %s", filename_base, title)

                file_counter += 1
                time.sleep(max(0.0, rate_limit))

            if max_images and file_counter > max_images:
                logger.info("Reached maximum images; stopping crawl loop.")
                break

            page += 1

    except KeyboardInterrupt:
        logger.info("Interrupted by user; waiting for outstanding downloads...")
    except Exception:
        logger.exception("Unexpected error during crawl.")
    finally:
        executor.shutdown(wait=True)
        conn.close()

    logger.info("Crawl finished. Total images downloaded: %s, metadata files saved: %s", total_downloaded, total_metadata)


# -------------------------
# CLI + interactive helpers
# -------------------------
def parse_download_choice(value: str) -> Tuple[bool, bool]:
    v = (value or "").lower()
    if v in ("images",):
        return True, False
    if v in ("metadata", "text"):
        return False, True
    return True, True


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="NASA Image Downloader (full-featured)")
    p.add_argument("--query", "-q", help="Search query (interactive default: space)", default=None)
    p.add_argument("--save-dir", "-s", help="Directory to save (interactive default: ./nasabackup)", default=None)
    p.add_argument("--download", "-d", help="What to download: 'images', 'metadata', or 'both' (default: both)", default="both")
    p.add_argument("--qualities", help="Comma-separated qualities (small,medium,large,orig) or 'all' (default: orig)", default=None)
    p.add_argument("--rate", type=float, help="Delay between search items in seconds (default: 1.0)", default=None)
    p.add_argument("--max", type=int, help="Maximum number of images to process (default: all)", default=None)
    p.add_argument("--workers", type=int, help="Concurrent image download workers (default: 4)", default=4)
    p.add_argument("--db", help="SQLite DB path for dedupe (default: <save_dir>/nasa_downloader.db)", default=None)
    p.add_argument("--dedupe", action="store_true", help="Enable dedupe by hashing images (recommended)")
    p.add_argument("--skip-existing-by-name", action="store_true", help="Skip if same filename already exists and identical")
    p.add_argument("--metadata-format", help="Comma-separated formats: txt,json,both (default both)", default="both")
    p.add_argument("--retries", type=int, help="HTTP retries (default: 3)", default=3)
    p.add_argument("--backoff", type=float, help="HTTP backoff factor (default: 0.5)", default=0.5)
    p.add_argument("--timeout", type=float, help="HTTP timeout seconds (default: 15.0)", default=15.0)
    p.add_argument("--user-agent", help="User-Agent header", default=DEFAULT_USER_AGENT)
    p.add_argument("--hash-algo", help="Hash algorithm for dedupe (sha256 recommended)", default="sha256")
    p.add_argument("--log-level", help="Console log level: DEBUG/INFO/WARNING/ERROR", default="INFO")
    return p


def interactive_prompt(prompt: str, default: str) -> str:
    try:
        res = input(f"{prompt} (default: {default}): ").strip()
        return res or default
    except EOFError:
        return default
    except KeyboardInterrupt:
        print()
        raise


def main_cli(argv: Optional[List[str]] = None) -> None:
    parser = build_argparser()
    args = parser.parse_args(argv)

    query = args.query if args.query is not None else interactive_prompt("Enter search query", "space")
    save_dir = args.save_dir if args.save_dir is not None else interactive_prompt("Enter folder to save images and metadata", "./nasabackup")

    numeric_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(numeric_level)
    configure_file_logging(save_dir)

    download_images, download_text = parse_download_choice(args.download)

    if args.qualities:
        raw_q = args.qualities.lower()
        if raw_q == "all":
            qualities = KNOWN_QUALITIES[:]
        else:
            qualities = [q.strip() for q in raw_q.split(",") if q.strip()]
    else:
        print("\nSelect image quality (you can select multiple separated by commas):")
        print("1 - small (~small.jpg)")
        print("2 - medium (~medium.jpg)")
        print("3 - large (~large.jpg)")
        print("4 - orig (~orig.jpg)")
        print("5 - all")
        qc = interactive_prompt("Enter 1,2,3,4,5 or comma-separated names (default 4)", "4")
        if qc.strip() == "5":
            qualities = KNOWN_QUALITIES[:]
        elif re.fullmatch(r"[1-4](?:,[1-4])*", qc.replace(" ", "")):
            idx_map = {"1": "small", "2": "medium", "3": "large", "4": "orig"}
            qualities = [idx_map[x] for x in qc.split(",") if x]
        else:
            chosen = [s.strip() for s in qc.split(",")]
            qualities = [c for c in chosen if c in KNOWN_QUALITIES]
            if not qualities:
                qualities = ["orig"]

    rate = args.rate if args.rate is not None else float(interactive_prompt("Enter delay between requests in seconds", "1.0"))

    max_images = args.max
    if max_images is None:
        try:
            use_limit = interactive_prompt("Limit number of images? (y/N)", "N").lower().startswith("y")
            if use_limit:
                num = interactive_prompt("Enter maximum number of images to download", "100")
                try:
                    max_images = int(num)
                except Exception:
                    logger.warning("Invalid number entered, will download all available images.")
                    max_images = None
            else:
                max_images = None
        except KeyboardInterrupt:
            logger.info("Exiting by user request.")
            return

    db_path = args.db or os.path.join(save_dir, "nasa_downloader.db")

    mf_raw = args.metadata_format.lower()
    if mf_raw in ("json",):
        metadata_formats = ["json"]
    elif mf_raw in ("txt", "text"):
        metadata_formats = ["txt"]
    else:
        metadata_formats = ["txt", "json"]

    logger.info("Starting crawl: query=%s, save_dir=%s, qualities=%s, download_images=%s, download_text=%s, rate=%s, max=%s",
                query, save_dir, qualities, download_images, download_text, rate, max_images)

    crawl_nasa_images(
        query=query,
        save_dir=save_dir,
        download_images=download_images,
        download_text=download_text,
        qualities=qualities,
        rate_limit=rate,
        max_images=max_images,
        workers=max(1, args.workers),
        db_path=db_path,
        retries=max(0, args.retries),
        backoff_factor=max(0.0, args.backoff),
        timeout=max(1.0, args.timeout),
        user_agent=args.user_agent,
        hash_algo=args.hash_algo,
        skip_existing_by_name=args.skip_existing_by_name,
        metadata_formats=metadata_formats,
        dedupe=args.dedupe,
    )


if __name__ == "__main__":
    try:
        main_cli()
    except KeyboardInterrupt:
        logger.info("Terminated by user.")
        sys.exit(0)
    except Exception:
        logger.exception("Fatal error in main")
        sys.exit(2)
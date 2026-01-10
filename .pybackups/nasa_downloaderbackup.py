#!/usr/bin/env python3
"""
NASA Image Download Tool - final polished single-file implementation.

Behavior changes from earlier versions:
- Default output folder (when --output is omitted) is created next to the script:
  <script_folder>/nasabackup
- The interactive prompt still shows a short default hint ("./nasabackup") but the actual default
  resolves to the script folder (so running from other working directories won't put files in system folders).
- The tool prints a one-line startup log showing the exact folder that will be used.
- Robust logging (console + rotating file fallback), retries for downloads, progress bar, and safe fallbacks
  if the chosen directory is not writable.

Usage:
- Interactive: python nasa_downloader.py
- CLI: python nasa_downloader.py --query "mars" --limit 10
- Non-interactive default: python nasa_downloader.py --no-prompt --query "moon"
"""

from __future__ import annotations
import argparse
import json
import logging
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from tqdm import tqdm

# Constants
DEFAULT_SUBDIR = "nasabackup"
LOG_SUBDIR = "logs"
LOG_FILENAME = "nasa_downloader.log"
API_SEARCH_URL = "https://images-api.nasa.gov/search"
API_ASSET_URL = "https://images-api.nasa.gov/asset"  # /{nasa_id}
QUALITY_SUFFIXES = {
    "small": "~small",
    "medium": "~medium",
    "large": "~large",
    "orig": "~orig",
}


# --- Utilities ----------------------------------------------------------------

def sanitize_filename(s: str, max_len: int = 120) -> str:
    s = re.sub(r"[^\w\s\-_.()]", "", s)  # allow some common filename chars
    s = s.strip().replace(" ", "_")
    return s[:max_len] or "item"


def ensure_writable_dir(path: Path) -> Path:
    """
    Ensure the path exists and is writable. If not possible, fallback to home/<DEFAULT_SUBDIR> or temp dir.
    Returns the path actually used.
    """
    candidates = [path, Path.home() / DEFAULT_SUBDIR, Path(tempfile.gettempdir()) / f"{DEFAULT_SUBDIR}_temp"]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test_file = candidate / ".write_test"
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("ok")
            try:
                test_file.unlink()
            except Exception:
                pass
            return candidate.resolve()
        except Exception:
            continue
    # final fallback: mkdtemp
    final = Path(tempfile.mkdtemp(prefix="nasabackup_"))
    return final.resolve()


def configure_logging(base_dir: Path) -> None:
    """
    Configure console logging and attempt to add a rotating file handler in base_dir/logs.
    If file logging fails, continue with console logging only.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
    logs_dir = base_dir / LOG_SUBDIR
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(filename=str(logs_dir / LOG_FILENAME), maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logging.getLogger().addHandler(fh)
        logging.getLogger().info("File logging enabled at %s", logs_dir / LOG_FILENAME)
    except Exception as exc:
        logging.getLogger().warning("Could not enable file logging (%s); continuing with console logging.", exc)


# --- NASA API helpers --------------------------------------------------------

@dataclass
class NasaItem:
    nasa_id: str
    title: str
    description: str
    date_created: str
    center: str
    keywords: List[str]
    raw: Dict


class NasaAPI:
    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "nasa-image-downloader/1.0"})

    def search(self, query: str, page: int = 1, media_type: str = "image") -> Tuple[List[NasaItem], bool]:
        """
        Search NASA Images API. Returns (items, more_pages_available_flag).
        """
        try:
            resp = self.session.get(API_SEARCH_URL, params={"q": query, "media_type": media_type, "page": page}, timeout=15)
            resp.raise_for_status()
            payload = resp.json()
            items = payload.get("collection", {}).get("items", [])
            results = []
            for it in items:
                d = it.get("data", [{}])[0]
                results.append(
                    NasaItem(
                        nasa_id=d.get("nasa_id", "unknown"),
                        title=d.get("title", "No Title"),
                        description=d.get("description", ""),
                        date_created=d.get("date_created", ""),
                        center=d.get("center", ""),
                        keywords=d.get("keywords", []) or [],
                        raw=d,
                    )
                )
            more = len(items) > 0
            return results, more
        except Exception as e:
            logging.getLogger().error("Search failed for page %s: %s", page, e)
            return [], False

    def get_asset_urls(self, nasa_id: str) -> List[str]:
        """
        Use the NASA asset endpoint to list available asset URLs for a nasa_id.
        Falls back to an empty list on error.
        """
        try:
            resp = self.session.get(f"{API_ASSET_URL}/{nasa_id}", timeout=15)
            resp.raise_for_status()
            payload = resp.json()
            items = payload.get("collection", {}).get("items", [])
            urls = []
            for item in items:
                href = item.get("href")
                if href:
                    urls.append(href)
            return urls
        except Exception:
            return []


# --- Download & file helpers -------------------------------------------------

def find_urls_for_qualities(urls: List[str], qualities: List[str]) -> List[str]:
    selected: List[str] = []
    for q in qualities:
        if q not in QUALITY_SUFFIXES:
            continue
        suff = QUALITY_SUFFIXES[q]
        for u in urls:
            if suff in u.lower():
                selected.append(u)
                break
    if selected:
        return selected

    image_exts = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif")
    image_urls = [u for u in urls if any(u.lower().endswith(ext) or f".{ext}?" in u.lower() for ext in [e.lstrip(".") for e in image_exts])]
    seen = set()
    out = []
    for u in image_urls:
        if u not in seen:
            out.append(u)
            seen.add(u)
        if len(out) >= max(1, len(qualities)):
            break
    if out:
        return out
    return urls[: max(1, len(qualities))]


def construct_quality_url(nasa_id: str, quality: str) -> Optional[str]:
    if quality not in QUALITY_SUFFIXES:
        return None
    url = f"https://images-assets.nasa.gov/image/{nasa_id}/{nasa_id}{QUALITY_SUFFIXES[quality]}.jpg"
    try:
        resp = requests.head(url, timeout=10)
        if resp.status_code == 200:
            return url
    except requests.RequestException:
        pass
    return None


def download_with_retries(url: str, dest: Path, session: Optional[requests.Session] = None, retries: int = 3, chunk_size: int = 8192) -> bool:
    session = session or requests.Session()
    for attempt in range(1, retries + 1):
        try:
            with session.get(url, stream=True, timeout=20) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length") or 0)
                dest.parent.mkdir(parents=True, exist_ok=True)
                mode = "wb"
                if total:
                    with open(dest, mode) as fh:
                        for chunk in tqdm(r.iter_content(chunk_size=chunk_size), total=(total // chunk_size) + 1, unit="KB", desc=dest.name, leave=False):
                            if chunk:
                                fh.write(chunk)
                else:
                    with open(dest, mode) as fh:
                        for chunk in r.iter_content(chunk_size=chunk_size):
                            if chunk:
                                fh.write(chunk)
            logging.getLogger().info("Downloaded: %s -> %s", url, dest)
            return True
        except Exception as exc:
            logging.getLogger().warning("Attempt %s failed for %s: %s", attempt, url, exc)
            time.sleep(1 + attempt)
    logging.getLogger().error("Giving up on %s after %s attempts", url, retries)
    return False


def save_metadata_files(dest_dir: Path, filename_base: str, metadata: Dict) -> Tuple[Path, Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    json_path = dest_dir / f"{filename_base}.json"
    txt_path = dest_dir / f"{filename_base}.txt"
    try:
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2, ensure_ascii=False)
    except Exception as exc:
        logging.getLogger().warning("Failed to save JSON metadata %s: %s", json_path, exc)
    try:
        with open(txt_path, "w", encoding="utf-8") as fh:
            for k, v in metadata.items():
                fh.write(f"{k}: {v}\n")
    except Exception as exc:
        logging.getLogger().warning("Failed to save TXT metadata %s: %s", txt_path, exc)
    return json_path, txt_path


# --- High-level crawl function -----------------------------------------------

def crawl_nasa_images(
    query: str,
    main_save_dir: Path,
    download_images: bool,
    download_metadata: bool,
    qualities: List[str],
    rate_limit: float = 1.0,
    max_images: Optional[int] = None,
    session: Optional[requests.Session] = None,
):
    api = NasaAPI(session=session or requests.Session())
    main_save_dir = ensure_writable_dir(main_save_dir)
    configure_logging(main_save_dir)
    logging.getLogger().info("Using output folder: %s", main_save_dir)

    quality_folder_map = {"small": "Low", "medium": "Medium", "large": "High", "orig": "Original"}
    quality_dirs = {}
    for q in qualities:
        label = quality_folder_map.get(q, q)
        q_dir = main_save_dir / label
        images_dir = q_dir / "Images"
        metadata_dir = q_dir / "Metadata"
        images_dir.mkdir(parents=True, exist_ok=True)
        metadata_dir.mkdir(parents=True, exist_ok=True)
        quality_dirs[q] = {"images": images_dir, "metadata": metadata_dir}

    page = 1
    file_counter = 1
    total_downloaded = 0
    total_metadata = 0

    while True:
        logging.getLogger().info("Fetching page %s for query '%s'...", page, query)
        items, more = api.search(query=query, page=page)
        if not items:
            logging.getLogger().info("No items found on page %s — stopping.", page)
            break

        for item in items:
            if max_images and file_counter > max_images:
                logging.getLogger().info("Reached requested image limit (%s).", max_images)
                print_summary(total_downloaded, total_metadata)
                return

            nasa_id = item.nasa_id
            title = item.title
            description = item.description or ""
            metadata = {
                "NASA ID": nasa_id,
                "Title": title,
                "Description": description,
                "Date Created": item.date_created,
                "Center": item.center,
                "Keywords": ", ".join(item.keywords or []),
            }

            filename_base = f"{file_counter:04d}_{sanitize_filename(title)[:60]}"
            downloaded_any = False

            urls = api.get_asset_urls(nasa_id)
            chosen_urls_by_quality = {q: [] for q in qualities}
            if urls:
                matched = find_urls_for_qualities(urls, qualities)
                for q in qualities:
                    q_urls = [u for u in matched if QUALITY_SUFFIXES.get(q, "") in u.lower()]
                    if q_urls:
                        chosen_urls_by_quality[q] = q_urls
                    else:
                        c = construct_quality_url(nasa_id, q)
                        if c:
                            chosen_urls_by_quality[q] = [c]
            else:
                for q in qualities:
                    c = construct_quality_url(nasa_id, q)
                    if c:
                        chosen_urls_by_quality[q] = [c]

            if download_images:
                for q in qualities:
                    for url in chosen_urls_by_quality.get(q, []):
                        ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
                        dest = quality_dirs[q]["images"] / f"{filename_base}{ext}"
                        if dest.exists():
                            logging.getLogger().info("Skipping already downloaded file: %s", dest)
                            downloaded_any = True
                            continue
                        ok = download_with_retries(url, dest, session=session)
                        if ok:
                            downloaded_any = True
                            total_downloaded += 1
                        else:
                            logging.getLogger().warning("Failed to download %s at quality %s", nasa_id, q)

            if download_metadata:
                save_metadata_files(quality_dirs[qualities[0]]["metadata"], filename_base, metadata)
                total_metadata += 1

            if downloaded_any or download_metadata:
                print(f"Saved {filename_base}: {title}")

            file_counter += 1
            time.sleep(rate_limit)

        page += 1
        if not more:
            break

    print_summary(total_downloaded, total_metadata)


def print_summary(total_downloaded: int, total_metadata: int) -> None:
    print("\nDone!")
    print(f"Total images downloaded: {total_downloaded}")
    print(f"Total metadata files saved: {total_metadata}")


# --- CLI / main ---------------------------------------------------------------

def parse_quality_input(choice: Optional[str]) -> List[str]:
    mapping = {"1": "small", "2": "medium", "3": "large", "4": "orig", "5": "all"}
    if not choice:
        return ["orig"]
    choice = choice.strip().lower()
    if choice == "5" or choice == "all":
        return ["small", "medium", "large", "orig"]
    parts = [p.strip() for p in choice.split(",") if p.strip()]
    out = []
    for p in parts:
        out.append(mapping.get(p, p if p in QUALITY_SUFFIXES else "orig"))
    seen = set()
    final = []
    for x in out:
        if x not in seen:
            final.append(x)
            seen.add(x)
    return final or ["orig"]


def interactive_prompt(prompt: str, default: str = "") -> str:
    print(prompt, end=" ")
    val = input().strip()
    return val if val else default


def main(argv=None):
    try:
        parser = argparse.ArgumentParser(description="NASA Image Download Tool")
        parser.add_argument("--query", "-q", help="Search query (default interactive)", default=None)
        parser.add_argument("--output", "-o", help="Output folder (default: script_folder/nasabackup)", default=None)
        parser.add_argument("--qualities", "-Q", help="Qualities (1..5 or names, comma-separated). Default orig.", default=None)
        parser.add_argument("--limit", "-n", type=int, help="Max images to download (default: all)", default=None)
        parser.add_argument("--rate", type=float, help="Delay between downloads (seconds). Default 1.0", default=1.0)
        parser.add_argument("--images", action="store_true", help="Download images (if omitted, tool may still download metadata)")
        parser.add_argument("--metadata", action="store_true", help="Download metadata (JSON + TXT)")
        parser.add_argument("--no-prompt", action="store_true", help="Do not prompt interactively; requires --query")
        args = parser.parse_args(argv)

        if args.no_prompt and not args.query:
            print("Error: --no-prompt requires --query to be set.")
            sys.exit(2)

        # Script directory used as the basis for the default output folder
        script_dir = Path(__file__).resolve().parent
        default_output_dir = script_dir / DEFAULT_SUBDIR
        default_hint = f"./{DEFAULT_SUBDIR}"

        query = args.query or interactive_prompt("Enter search query (default: space):", "space")

        if args.output:
            output_input = args.output
        else:
            if args.no_prompt:
                output_input = str(default_output_dir)
            else:
                output_input = interactive_prompt(fr"Enter folder to save images and metadata (default: {default_hint} -> script folder):", default_hint)
                # If user accepted the hint default_hint (or left blank) we'll use the script folder default
                if output_input.strip() == "" or output_input.strip() == default_hint:
                    output_input = str(default_output_dir)

        # Resolve output: if user gave an absolute path use it; if relative, treat it relative to current working directory
        output_path = Path(output_input).expanduser()
        if not output_path.is_absolute():
            # Keep the intuitive behavior: relative paths are relative to current working directory
            output_path = (Path.cwd() / output_path).resolve()

        if args.qualities:
            qualities = parse_quality_input(args.qualities)
        else:
            q_choice = interactive_prompt("Select image quality: 1-small,2-medium,3-large,4-orig,5-all (default 4):", "4")
            qualities = parse_quality_input(q_choice)

        if args.images or args.metadata:
            download_images = args.images
            download_metadata = args.metadata
        else:
            print("\nWhat do you want to download?")
            print("1 - Images only")
            print("2 - Images and metadata")
            print("3 - Metadata only")
            choice = interactive_prompt("Enter 1, 2, or 3 (default 2):", "2")
            download_images = choice in ("1", "2")
            download_metadata = choice in ("2", "3")

        if args.limit is not None:
            max_images = args.limit
        else:
            print("\nHow many images do you want to download?")
            print("1 - All available images")
            print("2 - Specify number")
            amt = interactive_prompt("Enter 1 or 2 (default 1):", "1")
            if amt == "2":
                try:
                    v = int(interactive_prompt("Enter the maximum number of images to download:", "0"))
                    max_images = v if v > 0 else None
                except Exception:
                    max_images = None
            else:
                max_images = None

        try:
            rate_limit = float(interactive_prompt("Enter delay between requests in seconds (default 1.0):", str(args.rate or 1.0)))
        except Exception:
            rate_limit = args.rate or 1.0

        # Start crawling
        crawl_nasa_images(
            query=query,
            main_save_dir=output_path,
            download_images=download_images,
            download_metadata=download_metadata,
            qualities=qualities,
            rate_limit=rate_limit,
            max_images=max_images,
        )
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting.")
        sys.exit(1)


if __name__ == "__main__":
    main()
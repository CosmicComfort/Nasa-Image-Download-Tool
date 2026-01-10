#!/usr/bin/env python3
"""
NASA Image Download Tool - polished final single-file implementation

- Default root output folder: script_folder/NASA-Downloads
- Per-search organization: <root>/<sanitized_query>/<Quality>/{Images,Metadata}
- Concurrent downloads with adaptive throttling, retries and progress
- Nice command-deck themed interactive prompts
- Animated ASCII intro banner (moon + astronaut planting flag) with twinkling stars
- No new external dependencies: requires requests and tqdm (same as before)

Usage:
    python nasa_downloader.py            # interactive (shows ASCII intro)
    python nasa_downloader.py --query "mars" --no-prompt --workers 8
    python nasa_downloader.py --help

Note: The ASCII animation uses ANSI sequences. On Windows, modern terminals support them.
This script attempts to enable ANSI on Windows; if that fails it's still usable (animation will be plain).
"""

from __future__ import annotations
import argparse
import concurrent.futures
import json
import logging
import os
import random
import re
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

# ------------------------
# Configuration / Defaults
# ------------------------
DEFAULT_SUBDIR = "NASA-Downloads"
LOG_SUBDIR = "logs"
LOG_FILENAME = "nasa_downloader.log"
API_SEARCH_URL = "https://images-api.nasa.gov/search"
API_ASSET_URL = "https://images-api.nasa.gov/asset"
QUALITY_SUFFIXES = {"small": "~small", "medium": "~medium", "large": "~large", "orig": "~orig"}

# ------------------------
# Terminal / ASCII Intro
# ------------------------


def enable_ansi_on_windows():
    """
    Try to enable ANSI escape sequence processing on Windows consoles.
    It's best-effort; failures are ignored.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE = -11
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            new_mode = mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
            kernel32.SetConsoleMode(handle, new_mode)
    except Exception:
        pass


# Large ASCII art for moon scene with astronaut planting a flag.
# Designed to fit ~80 columns width. We'll overlay animated stars.
ASCII_ART = [
    r"                             .        .       *       .       .   ",
    r"         .        .   *           *       .       .    .       ",
    r"    .        .        .    .   .         .        .      *     ",
    r"          .                                  .   .       .     ",
    r"     .        .           .      .    .           .           ",
    r"                              .           .                  ",
    r"            _____                                      .      ",
    r"         .-'     '-.     _.-'\"\"\"\"\"\"\"\"-._                     ",
    r"       .'  _   _    '. .'\  .--.   .--. /'.    .             ",
    r"      /   (.) (.)     \\/  |(    ) (    )|  \\                 ",
    r"     |  .  .---.  .    |   \\ '--'   '--' /   |    .          ",
    r"     |  | (     ) |    |    '.___.___.__.'    |               ",
    r"      \\  ' `---'  /    |     ASTRONAUT      /    .           ",
    r"       '.       .'     /                   .'                ",
    r"         `-._.-'      /   .----.    .----. /                  ",
    r"    ~~~  MOON SURFACE ~~~   |FLAG|    |BASE|   ~~~~~      .   ",
    r"  ___________________________/____\\____/____\\________________",
    r" /___________________________________________________________\\",
    r"|   _  _       _      _   _       _   _    _   _    _    _   |",
    r"|  | || |     / \\    | | | |     | | | |  | | | |  / \\  | |  |",
    r"|  | || |    / _ \\   | |_| |     | |_| |  | |_| | / _ \\ |_|  |",
    r"|  |_||_|   /_/ \\_\\   \\___/       \\___/    \\___/ /_/ \\_\\_(_)  |",
    r"|_____________________________________________________________|",
]

BANNER_WIDTH = max(len(line) for line in ASCII_ART)
BANNER_HEIGHT = len(ASCII_ART)


def clear_screen():
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()


def hide_cursor():
    sys.stdout.write("\x1b[?25l")
    sys.stdout.flush()


def show_cursor():
    sys.stdout.write("\x1b[?25h")
    sys.stdout.flush()


def render_banner_with_stars(star_positions: List[Tuple[int, int]], width: int):
    """
    Render ASCII_ART with stars overlaid at given positions.
    star_positions: list of (row, col) relative to banner bounding box.
    width: console width (used for centering horizontally).
    Returns the final string to print (without clearing).
    """
    # Build a local mutable copy of artwork lines as char arrays
    canvas = [list(line.ljust(BANNER_WIDTH)) for line in ASCII_ART]
    # Overlay stars
    for r, c, ch in star_positions:
        if 0 <= r < BANNER_HEIGHT and 0 <= c < BANNER_WIDTH:
            canvas[r][c] = ch
    # Compose centered lines
    term_w = width
    out_lines = []
    pad_left = max(0, (term_w - BANNER_WIDTH) // 2)
    pad = " " * pad_left
    for line in canvas:
        out_lines.append(pad + "".join(line))
    return "\n".join(out_lines)


def generate_starfield(num_stars: int) -> List[Tuple[int, int, str]]:
    """
    Random star positions and initial glyphs. Glyph set includes subtle variations.
    """
    glyphs = ["·", ".", "*", "+", "✦", "✶"]
    stars = []
    for _ in range(num_stars):
        r = random.randrange(0, BANNER_HEIGHT)
        c = random.randrange(0, BANNER_WIDTH)
        ch = random.choice(glyphs)
        stars.append((r, c, ch))
    return stars


def twinkle_stars_loop(duration: float = 3.0, fps: float = 8.0):
    """
    Short animated intro showing twinkling stars over the ASCII art.
    Runs for 'duration' seconds at 'fps' frames per second.
    """
    try:
        enable_ansi_on_windows()
        hide_cursor()
        term_w = shutil_get_columns()
        # start with a baseline starfield
        base = generate_starfield(max(12, BANNER_WIDTH // 8))
        t0 = time.time()
        frame = 0
        while time.time() - t0 < duration:
            # small variation: toggle some stars, change glyphs
            stars = []
            for (r, c, _) in base:
                # 25% chance to change glyph/be off
                if random.random() < 0.20:
                    glyph = random.choice([".", "*", "+", "·"])
                else:
                    glyph = "."
                # occasional brighter star
                if random.random() < 0.06:
                    glyph = random.choice(["✦", "✶", "*"])
                stars.append((r, c, glyph))
            out = render_banner_with_stars(stars, term_w)
            clear_screen()
            # Add a top header with small title
            header = f"  [ NASA IMAGE DOWNLOADER - COMMAND DECK ]".center(term_w)
            print("\n" + header + "\n")
            print(out)
            # Add footer status line
            footer = "Tip: Press Ctrl+C to cancel at any time".center(term_w)
            print("\n" + footer)
            time.sleep(1.0 / max(1, fps))
            frame += 1
    finally:
        show_cursor()


def shutil_get_columns() -> int:
    """
    Safe terminal width detection (fallback to 80).
    """
    try:
        import shutil
        cols = shutil.get_terminal_size().columns
        return max(40, cols)
    except Exception:
        return 80


# ------------------------
# Networking / Sessions
# ------------------------


_thread_local = threading.local()


def make_session(pool_maxsize: int = 10, retries: int = 3, backoff_factor: float = 0.5) -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["HEAD", "GET", "OPTIONS"]),
    )
    adapter = HTTPAdapter(pool_connections=pool_maxsize, pool_maxsize=pool_maxsize, max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({"User-Agent": "nasa-image-downloader/1.0"})
    return s


def get_thread_session(pool_maxsize: int = 10, retries: int = 3, backoff_factor: float = 0.5) -> requests.Session:
    if not hasattr(_thread_local, "session"):
        _thread_local.session = make_session(pool_maxsize=pool_maxsize, retries=retries, backoff_factor=backoff_factor)
    return _thread_local.session


# ------------------------
# Adaptive controller
# ------------------------


class AdaptiveController:
    def __init__(self, min_workers: int = 1, max_workers: int = 12):
        self.lock = threading.Lock()
        self.success = 0
        self.fail = 0
        self.throttle = 0
        self.total = 0
        self.min_workers = min_workers
        self.max_workers = max_workers

    def report(self, status: str) -> None:
        with self.lock:
            self.total += 1
            if status == "success":
                self.success += 1
            elif status == "throttle":
                self.throttle += 1
            else:
                self.fail += 1

    def evaluate_and_adjust(self, current_workers: int) -> Tuple[int, float]:
        with self.lock:
            total = self.total or 1
            succ = self.success
            thr = self.throttle
            fail = self.fail
            thr_rate = thr / total
            fail_rate = (fail + thr) / total
            succ_rate = succ / total
            # reset
            self.success = self.fail = self.throttle = self.total = 0

        new_workers = current_workers
        cooldown = 0.0

        if thr_rate > 0.08:
            new_workers = max(self.min_workers, int(current_workers * 0.5))
            cooldown = min(60, 5 + int(thr_rate * 200))
            logging.getLogger().warning(
                "High throttle rate %.1f%% -> reducing workers to %s, cooldown %ss", thr_rate * 100, new_workers, cooldown
            )
            return new_workers, cooldown

        if fail_rate > 0.25:
            new_workers = max(self.min_workers, int(current_workers * 0.7))
            cooldown = min(30, 3 + int(fail_rate * 40))
            logging.getLogger().warning(
                "High failure rate %.1f%% -> reducing workers to %s, cooldown %ss", fail_rate * 100, new_workers, cooldown
            )
            return new_workers, cooldown

        if succ_rate > 0.95 and current_workers < self.max_workers:
            new_workers = min(self.max_workers, current_workers + 1)
            logging.getLogger().info("High success rate %.1f%% -> increasing workers to %s", succ_rate * 100, new_workers)
            return new_workers, 0.0

        return new_workers, cooldown


# ------------------------
# NASA API helpers & download logic
# ------------------------


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
        self.session = session or make_session()

    def search(self, query: str, page: int = 1, media_type: str = "image") -> Tuple[List[NasaItem], bool]:
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
        try:
            resp = self.session.get(f"{API_ASSET_URL}/{nasa_id}", timeout=15)
            resp.raise_for_status()
            payload = resp.json()
            items = payload.get("collection", {}).get("items", [])
            urls = [item.get("href") for item in items if item.get("href")]
            return urls
        except Exception:
            return []


def sanitize_filename(s: str, max_len: int = 120) -> str:
    s = s or ""
    s = s.strip().lower()
    s = re.sub(r"[^\w\s\-_.()]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s[:max_len] or "item"


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


def _download_task(url: str, dest: Path, controller: Optional[AdaptiveController], chunk_size: int = 65536, retries: int = 3) -> bool:
    session = get_thread_session(pool_maxsize=10, retries=max(1, retries), backoff_factor=0.5)
    for attempt in range(1, retries + 1):
        try:
            with session.get(url, stream=True, timeout=30) as r:
                if r.status_code == 429:
                    if controller:
                        controller.report("throttle")
                    logging.getLogger().warning("Received 429 for %s", url)
                    time.sleep(min(30, 1 + 2 ** attempt))
                    continue
                r.raise_for_status()
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if chunk:
                            fh.write(chunk)
            if controller:
                controller.report("success")
            logging.getLogger().info("Downloaded: %s -> %s", url, dest)
            return True
        except requests.RequestException as exc:
            logging.getLogger().warning("Attempt %s failed for %s: %s", attempt, url, exc)
            time.sleep(min(10, 0.5 * (2 ** attempt)))
        except Exception as exc:
            logging.getLogger().warning("Attempt %s error for %s: %s", attempt, url, exc)
            time.sleep(min(10, 0.5 * (2 ** attempt)))
    if controller:
        controller.report("fail")
    logging.getLogger().error("Giving up on %s after %s attempts", url, retries)
    return False


def download_urls_concurrent(url_dest_pairs: List[Tuple[str, Path]], workers: int = 6, controller: Optional[AdaptiveController] = None) -> int:
    success_count = 0
    if not url_dest_pairs:
        return 0
    total = len(url_dest_pairs)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as exe:
        futures = [exe.submit(_download_task, url, dest, controller) for url, dest in url_dest_pairs]
        for fut in tqdm(concurrent.futures.as_completed(futures), total=total, desc="Downloading", unit="file"):
            try:
                ok = fut.result()
                if ok:
                    success_count += 1
            except Exception as exc:
                logging.getLogger().exception("Download task raised: %s", exc)
    return success_count


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


# ------------------------
# Crawl / orchestration
# ------------------------


def ensure_writable_dir(path: Path) -> Path:
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
    final = Path(tempfile.mkdtemp(prefix=f"{DEFAULT_SUBDIR}_"))
    return final.resolve()


def configure_logging(base_dir: Path) -> None:
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


def crawl_nasa_images(
    query: str,
    main_save_dir: Path,
    download_images: bool,
    download_metadata: bool,
    qualities: List[str],
    rate_limit: float = 1.0,
    max_images: Optional[int] = None,
    workers: int = 6,
    min_workers: int = 1,
    max_workers: int = 12,
    adaptive: bool = True,
    session: Optional[requests.Session] = None,
):
    top_session = session or make_session(pool_maxsize=max(4, workers // 2), retries=3, backoff_factor=0.5)
    api = NasaAPI(session=top_session)

    # Ensure root exists
    main_save_dir = ensure_writable_dir(main_save_dir)

    # Create per-search folder
    sanitized_query = sanitize_filename(query) or "search"
    search_dir = main_save_dir / sanitized_query
    search_dir = ensure_writable_dir(search_dir)

    # Configure logging to search specific folder
    configure_logging(search_dir)

    logging.getLogger().info("Search output folder: %s", search_dir)
    logging.getLogger().info("Starting with %s worker(s); adaptive=%s", workers, adaptive)

    controller = AdaptiveController(min_workers=min_workers, max_workers=max_workers) if adaptive else None

    quality_folder_map = {"small": "Low", "medium": "Medium", "large": "High", "orig": "Original"}
    quality_dirs = {}
    for q in qualities:
        label = quality_folder_map.get(q, q)
        q_dir = search_dir / label
        images_dir = q_dir / "Images"
        metadata_dir = q_dir / "Metadata"
        images_dir.mkdir(parents=True, exist_ok=True)
        metadata_dir.mkdir(parents=True, exist_ok=True)
        quality_dirs[q] = {"images": images_dir, "metadata": metadata_dir}

    page = 1
    file_counter = 1
    total_downloaded = 0
    total_metadata = 0
    current_workers = workers

    while True:
        logging.getLogger().info("Fetching page %s for query '%s'...", page, query)
        items, more = api.search(query=query, page=page)
        if not items:
            logging.getLogger().info("No items found on page %s — stopping.", page)
            break

        page_url_dest_pairs: List[Tuple[str, Path]] = []

        for item in items:
            if max_images and file_counter > max_images:
                logging.getLogger().info("Reached requested image limit (%s).", max_images)
                if download_images and page_url_dest_pairs:
                    total_downloaded += download_urls_concurrent(page_url_dest_pairs, workers=current_workers, controller=controller)
                print_summary(total_downloaded, total_metadata)
                return

            nasa_id = item.nasa_id
            title = item.title
            metadata = {
                "NASA ID": nasa_id,
                "Title": title,
                "Description": item.description or "",
                "Date Created": item.date_created,
                "Center": item.center,
                "Keywords": ", ".join(item.keywords or []),
            }

            filename_base = f"{file_counter:04d}_{sanitize_filename(title)[:60]}"
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
                            continue
                        page_url_dest_pairs.append((url, dest))

            if download_metadata:
                save_metadata_files(quality_dirs[qualities[0]]["metadata"], filename_base, metadata)
                total_metadata += 1

            if download_images or download_metadata:
                print(f"Queued {filename_base}: {title}")

            file_counter += 1
            time.sleep(rate_limit)

        if download_images and page_url_dest_pairs:
            downloaded = download_urls_concurrent(page_url_dest_pairs, workers=current_workers, controller=controller)
            total_downloaded += downloaded

        if adaptive and controller:
            new_workers, cooldown = controller.evaluate_and_adjust(current_workers)
            if new_workers != current_workers:
                logging.getLogger().info("Adjusting worker count %s -> %s", current_workers, new_workers)
                current_workers = new_workers
            if cooldown and cooldown > 0:
                logging.getLogger().warning("Sleeping for %s seconds due to throttling/failures.", cooldown)
                time.sleep(cooldown)

        page += 1
        if not more:
            break

    print_summary(total_downloaded, total_metadata)


def print_summary(total_downloaded: int, total_metadata: int) -> None:
    print("\n=== Summary ===")
    print(f"Total images downloaded: {total_downloaded}")
    print(f"Total metadata files saved: {total_metadata}")
    print("================")


# ------------------------
# CLI, prompts & run
# ------------------------


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


def themed_input(prompt: str, default: str = "") -> str:
    """
    Themed command-deck prompt. Shows default when provided.
    """
    hint = f" [{default}]" if default else ""
    sys.stdout.write(f"\n\x1b[36mCOMMAND DECK>\x1b[0m {prompt}{hint}\n\x1b[33mCaptain>\x1b[0m ")
    sys.stdout.flush()
    try:
        val = input().strip()
    except EOFError:
        val = ""
    return val if val else default


def main(argv=None):
    try:
        parser = argparse.ArgumentParser(description="NASA Image Download Tool (polished)")
        parser.add_argument("--query", "-q", help="Search query (default interactive)", default=None)
        parser.add_argument("--output", "-o", help="Root output folder (default: script_folder/NASA-Downloads)", default=None)
        parser.add_argument("--qualities", "-Q", help="Qualities (1..5 or names, comma-separated). Default orig.", default=None)
        parser.add_argument("--limit", "-n", type=int, help="Max images to download (default: all)", default=None)
        parser.add_argument("--rate", type=float, help="Delay between processing items/pages in seconds (default 1.0)", default=1.0)
        parser.add_argument("--workers", type=int, help="Initial concurrent download worker threads (default 6, max 12)", default=6)
        parser.add_argument("--min-workers", type=int, help="Minimum allowed workers when adapting (default 1)", default=1)
        parser.add_argument("--max-workers", type=int, help="Maximum allowed workers when adapting (default 12)", default=12)
        parser.add_argument("--no-adaptive", action="store_true", help="Disable adaptive throttling")
        parser.add_argument("--images", action="store_true", help="Download images")
        parser.add_argument("--metadata", action="store_true", help="Download metadata (JSON + TXT)")
        parser.add_argument("--no-prompt", action="store_true", help="Do not prompt interactively; requires --query")
        args = parser.parse_args(argv)

        if args.no_prompt and not args.query:
            print("Error: --no-prompt requires --query to be set.")
            sys.exit(2)

        initial_workers = max(1, min(12, int(args.workers or 6)))
        min_workers = max(1, int(args.min_workers or 1))
        max_workers = max(min_workers, int(args.max_workers or 12))
        if max_workers > 32:
            max_workers = 32

        # Show animated intro only for interactive mode (not --no-prompt)
        if not args.no_prompt:
            try:
                twinkle_stars_loop(duration=3.2, fps=10)
            except KeyboardInterrupt:
                # allow user to interrupt animation and continue to prompts
                pass

        script_dir = Path(__file__).resolve().parent
        default_output_dir = script_dir / DEFAULT_SUBDIR
        default_hint = f"./{DEFAULT_SUBDIR}"

        query = args.query or themed_input("Enter search query (default: space):", "space")

        if args.output:
            output_input = args.output
        else:
            if args.no_prompt:
                output_input = str(default_output_dir)
            else:
                oi = themed_input(f"Enter folder to save images and metadata (default: {default_hint} -> script folder):", default_hint)
                if oi.strip() == "" or oi.strip() == default_hint:
                    output_input = str(default_output_dir)
                else:
                    output_input = oi

        output_path = Path(output_input).expanduser()
        if not output_path.is_absolute():
            output_path = (Path.cwd() / output_path).resolve()

        if args.qualities:
            qualities = parse_quality_input(args.qualities)
        else:
            q_choice = themed_input("Select image quality: 1-small,2-medium,3-large,4-orig,5-all (default 4):", "4")
            qualities = parse_quality_input(q_choice)

        if args.images or args.metadata:
            download_images = args.images
            download_metadata = args.metadata
        else:
            print("\n\x1b[35mWhat do you want to download?\x1b[0m")
            print("  1 - Images only")
            print("  2 - Images and metadata")
            print("  3 - Metadata only")
            choice = themed_input("Enter 1, 2, or 3 (default 2):", "2")
            download_images = choice in ("1", "2")
            download_metadata = choice in ("2", "3")

        if args.limit is not None:
            max_images = args.limit
        else:
            print("\n\x1b[35mHow many images do you want to download?\x1b[0m")
            print("  1 - All available images")
            print("  2 - Specify number")
            amt = themed_input("Enter 1 or 2 (default 1):", "1")
            if amt == "2":
                try:
                    v = int(themed_input("Enter the maximum number of images to download:", "0"))
                    max_images = v if v > 0 else None
                except Exception:
                    max_images = None
            else:
                max_images = None

        try:
            rate_limit = float(themed_input("Enter delay between requests in seconds (default 1.0):", str(args.rate or 1.0)))
        except Exception:
            rate_limit = args.rate or 1.0

        adaptive = not args.no_adaptive

        # Final startup log summary
        print("\n\x1b[32mInitializing mission parameters...\x1b[0m")
        print(f"  Query: {query}")
        print(f"  Output root: {output_path}")
        print(f"  Qualities: {qualities}")
        print(f"  Download images: {download_images} | Download metadata: {download_metadata}")
        print(f"  Workers: {initial_workers} (adaptive: {adaptive})\n")

        crawl_nasa_images(
            query=query,
            main_save_dir=output_path,
            download_images=download_images,
            download_metadata=download_metadata,
            qualities=qualities,
            rate_limit=rate_limit,
            max_images=max_images,
            workers=initial_workers,
            min_workers=min_workers,
            max_workers=max_workers,
            adaptive=adaptive,
        )
    except KeyboardInterrupt:
        print("\n\x1b[31mInterrupted by user. Exiting.\x1b[0m")
        sys.exit(1)


if __name__ == "__main__":
    main()
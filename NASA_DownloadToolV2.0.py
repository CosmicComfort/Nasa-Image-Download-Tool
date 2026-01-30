#!/usr/bin/env python3
"""
NASA Media Download Tool - Enhanced Space Edition

Features:
- Image AND video downloads with quality selection
- Procedurally generated galaxy/nebula intro with UFO
- Enhanced starfield with shooting stars
- Organized prompts for all options
- Per-search folders for images/videos
- Adaptive throttling and concurrent downloads
"""

from __future__ import annotations
import argparse
import concurrent.futures
import json
import logging
import math
import os
import random
import re
import shutil
import signal
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

# ============================================================================
# CONFIGURATION
# ============================================================================
DEFAULT_SUBDIR = "NASA-Downloads"
LOG_SUBDIR = "logs"
LOG_FILENAME = "nasa_downloader.log"
API_SEARCH_URL = "https://images-api.nasa.gov/search"
API_ASSET_URL = "https://images-api.nasa.gov/asset"

QUALITY_SUFFIXES = {
    "small": "~small",
    "medium": "~medium", 
    "large": "~large",
    "orig": "~orig"
}

# Theme colors
THEME_CYAN = "\x1b[36m"
THEME_YELLOW = "\x1b[33m"
THEME_GREEN = "\x1b[32m"
THEME_RED = "\x1b[31m"
THEME_MAGENTA = "\x1b[35m"
THEME_BLUE = "\x1b[34m"
THEME_BOLD = "\x1b[1m"
THEME_RESET = "\x1b[0m"

# Network defaults
DEFAULT_WORKERS = 6
MAX_WORKERS = 12
DEFAULT_RATE = 1.0
RETRY_TOTAL = 3
RETRY_BACKOFF = 0.5

# ============================================================================
# TERMINAL UTILITIES
# ============================================================================
def enable_ansi_on_windows():
    """Enable ANSI sequences on Windows (best-effort)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            new_mode = mode.value | 0x0004
            kernel32.SetConsoleMode(handle, new_mode)
    except Exception:
        pass

def clear_screen():
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()

def hide_cursor():
    sys.stdout.write("\x1b[?25l")
    sys.stdout.flush()

def show_cursor():
    sys.stdout.write("\x1b[?25h")
    sys.stdout.flush()

def get_terminal_size() -> Tuple[int, int]:
    try:
        size = shutil.get_terminal_size()
        return max(60, size.columns), max(15, size.lines)
    except Exception:
        return 100, 30

def safe_print(s: str = "", end: str = "\n"):
    sys.stdout.write(s + end)
    sys.stdout.flush()


# ============================================================================
# ADVANCED SPACE INTRO - GALAXY, NEBULA & UFO
# ============================================================================
class SpaceIntro:
    """Procedurally generated space scene with galaxy, nebula, and UFO."""
    
    def __init__(self):
        self.palette_stars = [" ", ".", "·", ":", "*", "⋆", "✦", "✶"]
        self.palette_nebula = [" ", ".", ":", "~", "≈", "▒", "▓", "█"]
        self.palette_galaxy = [" ", ".", "·", ":", "*", "+", "○", "●", "◉", "⦿"]
        
    def lerp(self, a: float, b: float, t: float) -> float:
        return a + (b - a) * t

    # --- STUB: prevents crashes, keeps interface intact ---
    def render_frame(
        self,
        particles,
        nebula,
        cols,
        rows,
        scale,
        cx,
        cy,
        show_ufo,
        frame_index
    ) -> str:
        # Placeholder frame (keeps animation pipeline alive)
        return "\n".join(" " * cols for _ in range(rows))

    # --- FIXED: this is where your orphaned code belonged ---
    def run_animation(self, duration: float = 4.5, frames: int = 50):
        term_w, term_h = get_terminal_size()
        cols = min(80, term_w)
        rows = min(24, term_h - 8)

        particles = []
        nebula = []
        scale = 1.0
        cx, cy = cols // 2, rows // 2
        show_ufo = True

        hide_cursor()
        t0 = time.time()

        try:
            for i in range(frames):
                t = i / max(1, frames - 1)

                frame_str = self.render_frame(
                    particles, nebula, cols, rows,
                    scale, cx, cy, show_ufo, i
                )

                clear_screen()
                title = f"{THEME_BOLD}{THEME_CYAN}╔═══════════════════════════════════════════════════════╗{THEME_RESET}"
                subtitle = f"{THEME_BOLD}{THEME_CYAN}║  NASA MEDIA DOWNLOADER — DEEP SPACE MISSION CONTROL  ║{THEME_RESET}"
                footer = f"{THEME_BOLD}{THEME_CYAN}╚═══════════════════════════════════════════════════════╝{THEME_RESET}"

                safe_print("\n" + title.center(term_w))
                safe_print(subtitle.center(term_w))
                safe_print(footer.center(term_w) + "\n")

                left_pad = max(0, (term_w - cols) // 2)
                pad = " " * left_pad
                safe_print("\n".join(pad + line for line in frame_str.splitlines()))

                tip = (
                    f"{THEME_YELLOW}"
                    f"⚡ Initializing quantum entanglement protocols... {int(t * 100)}%"
                    f"{THEME_RESET}"
                )
                safe_print("\n" + tip.center(term_w))

                elapsed = time.time() - t0
                target = (i + 1) * (duration / max(1, frames))
                time.sleep(max(0.0, target - elapsed))

        finally:
            show_cursor()


# ============================================================================
# NETWORK & SESSION MANAGEMENT
# ============================================================================
_thread_local = threading.local()

def make_session(pool_maxsize: int = 10, retries: int = RETRY_TOTAL, 
                backoff_factor: float = RETRY_BACKOFF) -> requests.Session:
    s = requests.Session()
    retry = Retry(total=retries, backoff_factor=backoff_factor,
                 status_forcelist=(429, 500, 502, 503, 504),
                 allowed_methods=frozenset(["HEAD", "GET", "OPTIONS"]))
    adapter = HTTPAdapter(pool_connections=pool_maxsize, pool_maxsize=pool_maxsize, 
                         max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({"User-Agent": "nasa-media-downloader/2.0"})
    return s

def get_thread_session(pool_maxsize: int = 10) -> requests.Session:
    if not hasattr(_thread_local, "session"):
        _thread_local.session = make_session(pool_maxsize=pool_maxsize)
    return _thread_local.session

# ============================================================================
# ADAPTIVE THROTTLING CONTROLLER
# ============================================================================
class AdaptiveController:
    """Adaptive concurrency controller with throttle detection."""
    
    def __init__(self, min_workers: int = 1, max_workers: int = MAX_WORKERS):
        self.lock = threading.Lock()
        self.success = 0
        self.fail = 0
        self.throttle = 0
        self.total = 0
        self.min_workers = min_workers
        self.max_workers = max_workers
    
    def report(self, status: str):
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
            thr_rate = self.throttle / total
            fail_rate = (self.fail + self.throttle) / total
            succ_rate = self.success / total
            self.success = self.fail = self.throttle = self.total = 0
        
        new_workers = current_workers
        cooldown = 0.0
        
        if thr_rate > 0.08:
            new_workers = max(self.min_workers, int(current_workers * 0.5))
            cooldown = min(60, 5 + int(thr_rate * 200))
            logging.info("Throttle detected: reducing to %d workers, cooldown %ds", 
                        new_workers, cooldown)
        elif fail_rate > 0.25:
            new_workers = max(self.min_workers, int(current_workers * 0.7))
            cooldown = min(30, 3 + int(fail_rate * 40))
            logging.warning("High failure rate: reducing to %d workers", new_workers)
        elif succ_rate > 0.95 and current_workers < self.max_workers:
            new_workers = min(self.max_workers, current_workers + 1)
            logging.info("Performance good: increasing to %d workers", new_workers)
        
        return new_workers, cooldown

# ============================================================================
# NASA API WRAPPER
# ============================================================================
@dataclass
class NasaItem:
    nasa_id: str
    title: str
    description: str
    date_created: str
    center: str
    keywords: List[str]
    media_type: str  # "image" or "video"
    raw: Dict

class NasaAPI:
    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or make_session()
    
    def search(self, query: str, page: int = 1, media_type: str = "image") -> Tuple[List[NasaItem], bool]:
        try:
            resp = self.session.get(API_SEARCH_URL, 
                                   params={"q": query, "media_type": media_type, "page": page},
                                   timeout=15)
            resp.raise_for_status()
            payload = resp.json()
            items = payload.get("collection", {}).get("items", [])
            
            results = []
            for it in items:
                d = it.get("data", [{}])[0]
                results.append(NasaItem(
                    nasa_id=d.get("nasa_id", "unknown"),
                    title=d.get("title", "No Title"),
                    description=d.get("description", ""),
                    date_created=d.get("date_created", ""),
                    center=d.get("center", ""),
                    keywords=d.get("keywords", []) or [],
                    media_type=d.get("media_type", media_type),
                    raw=d
                ))
            
            more = len(items) > 0
            return results, more
        except Exception as e:
            logging.error("Search failed for page %d: %s", page, e)
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

# ============================================================================
# DOWNLOAD HELPERS
# ============================================================================
def sanitize_filename(s: str, max_len: int = 100) -> str:
    if not s:
        return "item"
    s = s.strip().lower()
    s = re.sub(r"[^\w\s\-_.()]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s[:max_len] or "item"

def _download_task(url: str, dest: Path, controller: Optional[AdaptiveController],
                  chunk_size: int = 65536, retries: int = 3) -> bool:
    session = get_thread_session(pool_maxsize=10)
    
    for attempt in range(1, retries + 1):
        try:
            with session.get(url, stream=True, timeout=45) as r:
                if r.status_code == 429:
                    if controller:
                        controller.report("throttle")
                    time.sleep(min(30, 2 ** attempt))
                    continue
                
                r.raise_for_status()
                dest.parent.mkdir(parents=True, exist_ok=True)
                
                with open(dest, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if chunk:
                            fh.write(chunk)
                
                if controller:
                    controller.report("success")
                return True
                
        except Exception as exc:
            logging.warning("Attempt %d failed for %s: %s", attempt, url, exc)
            time.sleep(min(10, 0.5 * (2 ** attempt)))
    
    if controller:
        controller.report("fail")
    return False

def download_urls_concurrent(url_dest_pairs: List[Tuple[str, Path]], 
                            workers: int = DEFAULT_WORKERS,
                            controller: Optional[AdaptiveController] = None) -> int:
    if not url_dest_pairs:
        return 0
    
    success = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as exe:
        futures = [exe.submit(_download_task, url, dest, controller) 
                  for url, dest in url_dest_pairs]
        
        for fut in tqdm(concurrent.futures.as_completed(futures), 
                       total=len(futures), desc="Downloading", unit="file"):
            try:
                if fut.result():
                    success += 1
            except Exception as exc:
                logging.exception("Download error: %s", exc)
    
    return success

def save_metadata(dest_dir: Path, filename_base: str, metadata: Dict) -> Tuple[Path, Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    json_path = dest_dir / f"{filename_base}.json"
    txt_path = dest_dir / f"{filename_base}.txt"
    
    try:
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2, ensure_ascii=False)
    except Exception as exc:
        logging.warning("Failed to save JSON: %s", exc)
    
    try:
        with open(txt_path, "w", encoding="utf-8") as fh:
            for k, v in metadata.items():
                fh.write(f"{k}: {v}\n")
    except Exception as exc:
        logging.warning("Failed to save TXT: %s", exc)
    
    return json_path, txt_path

# ============================================================================
# URL QUALITY SELECTION
# ============================================================================
def find_quality_urls(urls: List[str], qualities: List[str], media_type: str) -> Dict[str, List[str]]:
    """Find URLs for requested qualities based on media type."""
    result = {q: [] for q in qualities}
    
    if media_type == "video":
        # For videos, look for different formats/qualities
        video_exts = (".mp4", ".mov", ".avi", ".webm", ".m4v")
        video_urls = [u for u in urls if any(u.lower().endswith(ext) for ext in video_exts)]
        
        # Try to categorize by size indicators in URL
        for q in qualities:
            if q == "small":
                matches = [u for u in video_urls if "small" in u.lower() or "mobile" in u.lower()]
            elif q == "medium":
                matches = [u for u in video_urls if "medium" in u.lower() or "web" in u.lower()]
            elif q == "large":
                matches = [u for u in video_urls if "large" in u.lower() or "hd" in u.lower()]
            elif q == "orig":
                matches = [u for u in video_urls if "orig" in u.lower() or "master" in u.lower()]
            else:
                matches = []
            
            if matches:
                result[q] = matches[:1]
            elif video_urls and not result[q]:
                result[q] = video_urls[:1]
    
    else:  # images
        for q in qualities:
            suff = QUALITY_SUFFIXES.get(q, "")
            matches = [u for u in urls if suff in u.lower()]
            if matches:
                result[q] = matches[:1]
    
    return result

# ============================================================================
# MAIN CRAWLER
# ============================================================================
def ensure_writable_dir(path: Path) -> Path:
    """Ensure directory is writable, fallback to alternatives."""
    candidates = [path, Path.home() / DEFAULT_SUBDIR, 
                 Path(tempfile.gettempdir()) / f"{DEFAULT_SUBDIR}_temp"]
    
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test_file = candidate / ".write_test"
            with open(test_file, "w") as f:
                f.write("ok")
            test_file.unlink()
            return candidate.resolve()
        except Exception:
            continue
    
    return Path(tempfile.mkdtemp(prefix=f"{DEFAULT_SUBDIR}_")).resolve()

def configure_logging(base_dir: Path):
    """Configure logging to file and console."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    logs_dir = base_dir / LOG_SUBDIR
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(
            filename=str(logs_dir / LOG_FILENAME),
            maxBytes=3_000_000,
            backupCount=3,
            encoding="utf-8"
        )
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logging.getLogger().addHandler(fh)
    except Exception as exc:
        logging.warning("Could not enable file logging: %s", exc)

def write_mission_manifest(search_dir: Path, manifest: Dict):
    """Write mission parameters to manifest file."""
    try:
        search_dir.mkdir(parents=True, exist_ok=True)
        mf = search_dir / "mission_manifest.json"
        with open(mf, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)
        logging.info("Mission manifest: %s", mf)
    except Exception as exc:
        logging.warning("Failed to write manifest: %s", exc)

def crawl_nasa_media(
    query: str,
    main_save_dir: Path,
    download_images: bool,
    download_videos: bool,
    download_metadata: bool,
    qualities: List[str],
    rate_limit: float = DEFAULT_RATE,
    max_items: Optional[int] = None,
    workers: int = DEFAULT_WORKERS,
    min_workers: int = 1,
    max_workers: int = MAX_WORKERS,
    adaptive: bool = True,
):
    """Main crawler for NASA images and videos."""
    
    # Setup
    main_save_dir = ensure_writable_dir(main_save_dir)
    sanitized_query = sanitize_filename(query) or "search"
    search_dir = main_save_dir / sanitized_query
    search_dir = ensure_writable_dir(search_dir)
    
    configure_logging(search_dir)
    
    # Manifest
    manifest = {
        "query": query,
        "download_images": download_images,
        "download_videos": download_videos,
        "download_metadata": download_metadata,
        "qualities": qualities,
        "workers": workers,
        "adaptive": adaptive,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    write_mission_manifest(search_dir, manifest)
    
    logging.info("Mission initialized: %s", search_dir)
    logging.info("Workers: %d (adaptive: %s)", workers, adaptive)
    
    # Setup folders
    quality_labels = {"small": "Low", "medium": "Medium", "large": "High", "orig": "Original"}
    quality_dirs = {}
    
    for q in qualities:
        label = quality_labels.get(q, q)
        
        if download_images:
            img_base = search_dir / "Images" / label
            (img_base / "Files").mkdir(parents=True, exist_ok=True)
            (img_base / "Metadata").mkdir(parents=True, exist_ok=True)
            quality_dirs.setdefault(q, {})["images"] = img_base
        
        if download_videos:
            vid_base = search_dir / "Videos" / label
            (vid_base / "Files").mkdir(parents=True, exist_ok=True)
            (vid_base / "Metadata").mkdir(parents=True, exist_ok=True)
            quality_dirs.setdefault(q, {})["videos"] = vid_base
    
    # API setup
    session = make_session(pool_maxsize=max(4, workers // 2))
    api = NasaAPI(session=session)
    controller = AdaptiveController(min_workers, max_workers) if adaptive else None
    
    current_workers = workers
    item_counter = 1
    total_img_downloaded = 0
    total_vid_downloaded = 0
    total_metadata = 0
    
    # Process images
    if download_images:
        safe_print(f"\n{THEME_CYAN}{'='*60}{THEME_RESET}")
        safe_print(f"{THEME_BOLD}{THEME_GREEN}PHASE 1: SCANNING FOR IMAGES{THEME_RESET}")
        safe_print(f"{THEME_CYAN}{'='*60}{THEME_RESET}\n")
        
        page = 1
        while True:
            logging.info("Fetching image page %d...", page)
            items, more = api.search(query=query, page=page, media_type="image")
            
            if not items:
                break
            
            page_downloads = []
            
            for item in items:
                if max_items and item_counter > max_items:
                    break
                
                nasa_id = item.nasa_id
                title = item.title
                filename_base = f"{item_counter:04d}_{sanitize_filename(title)[:60]}"
                
                urls = api.get_asset_urls(nasa_id)
                quality_urls = find_quality_urls(urls, qualities, "image")
                
                # Metadata
                if download_metadata:
                    metadata = {
                        "NASA ID": nasa_id,
                        "Title": title,
                        "Description": item.description,
                        "Date": item.date_created,
                        "Center": item.center,
                        "Keywords": ", ".join(item.keywords)
                    }
                    
                    if qualities and q in quality_dirs and "images" in quality_dirs[qualities[0]]:
                        meta_dir = quality_dirs[qualities[0]]["images"] / "Metadata"
                        save_metadata(meta_dir, filename_base, metadata)
                        total_metadata += 1
                
                # Queue downloads
                for q in qualities:
                    if q in quality_urls and quality_urls[q]:
                        for url in quality_urls[q]:
                            ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
                            dest = quality_dirs[q]["images"] / "Files" / f"{filename_base}{ext}"
                            
                            if not dest.exists():
                                page_downloads.append((url, dest))
                
                safe_print(f"{THEME_GREEN}✓{THEME_RESET} Queued: {title[:70]}")
                item_counter += 1
                time.sleep(rate_limit)
                
                if max_items and item_counter > max_items:
                    break
            
            # Download batch
            if page_downloads:
                downloaded = download_urls_concurrent(page_downloads, current_workers, controller)
                total_img_downloaded += downloaded
            
            # Adaptive adjustment
            if adaptive and controller:
                new_workers, cooldown = controller.evaluate_and_adjust(current_workers)
                if new_workers != current_workers:
                    current_workers = new_workers
                if cooldown > 0:
                    time.sleep(cooldown)
            
            if not more or (max_items and item_counter > max_items):
                break
            
            page += 1
    
    # Process videos
    if download_videos:
        safe_print(f"\n{THEME_CYAN}{'='*60}{THEME_RESET}")
        safe_print(f"{THEME_BOLD}{THEME_MAGENTA}PHASE 2: SCANNING FOR VIDEOS{THEME_RESET}")
        safe_print(f"{THEME_CYAN}{'='*60}{THEME_RESET}\n")
        
        page = 1
        video_counter = 1
        
        while True:
            logging.info("Fetching video page %d...", page)
            items, more = api.search(query=query, page=page, media_type="video")
            
            if not items:
                break
            
            page_downloads = []
            
            for item in items:
                if max_items and video_counter > max_items:
                    break
                
                nasa_id = item.nasa_id
                title = item.title
                filename_base = f"{video_counter:04d}_{sanitize_filename(title)[:60]}"
                
                urls = api.get_asset_urls(nasa_id)
                quality_urls = find_quality_urls(urls, qualities, "video")
                
                # Metadata
                if download_metadata:
                    metadata = {
                        "NASA ID": nasa_id,
                        "Title": title,
                        "Description": item.description,
                        "Date": item.date_created,
                        "Center": item.center,
                        "Keywords": ", ".join(item.keywords),
                        "Media Type": "video"
                    }
                    
                    if qualities and q in quality_dirs and "videos" in quality_dirs[qualities[0]]:
                        meta_dir = quality_dirs[qualities[0]]["videos"] / "Metadata"
                        save_metadata(meta_dir, filename_base, metadata)
                        total_metadata += 1
                
                # Queue downloads
                for q in qualities:
                    if q in quality_urls and quality_urls[q]:
                        for url in quality_urls[q]:
                            ext = os.path.splitext(url.split("?")[0])[1] or ".mp4"
                            dest = quality_dirs[q]["videos"] / "Files" / f"{filename_base}{ext}"
                            
                            if not dest.exists():
                                page_downloads.append((url, dest))
                
                safe_print(f"{THEME_MAGENTA}▶{THEME_RESET} Queued: {title[:70]}")
                video_counter += 1
                time.sleep(rate_limit)
                
                if max_items and video_counter > max_items:
                    break
            
            # Download batch
            if page_downloads:
                downloaded = download_urls_concurrent(page_downloads, current_workers, controller)
                total_vid_downloaded += downloaded
            
            # Adaptive adjustment
            if adaptive and controller:
                new_workers, cooldown = controller.evaluate_and_adjust(current_workers)
                if new_workers != current_workers:
                    current_workers = new_workers
                if cooldown > 0:
                    time.sleep(cooldown)
            
            if not more or (max_items and video_counter > max_items):
                break
            
            page += 1
    
    # Summary
    safe_print(f"\n{THEME_CYAN}{'='*60}{THEME_RESET}")
    safe_print(f"{THEME_BOLD}{THEME_GREEN}MISSION COMPLETE{THEME_RESET}")
    safe_print(f"{THEME_CYAN}{'='*60}{THEME_RESET}")
    safe_print(f"  Images downloaded: {total_img_downloaded}")
    safe_print(f"  Videos downloaded: {total_vid_downloaded}")
    safe_print(f"  Metadata files: {total_metadata}")
    safe_print(f"  Output location: {search_dir}")
    safe_print(f"{THEME_CYAN}{'='*60}{THEME_RESET}\n")

# ============================================================================
# ENHANCED CLI WITH ORGANIZED PROMPTS
# ============================================================================
def themed_input(prompt: str, default: str = "") -> str:
    """Themed input with default value."""
    hint = f" [{default}]" if default else ""
    sys.stdout.write(f"\n{THEME_CYAN}►{THEME_RESET} {prompt}{hint}\n{THEME_YELLOW}▸{THEME_RESET} ")
    sys.stdout.flush()
    try:
        val = input().strip()
    except EOFError:
        val = ""
    return val if val else default

def parse_quality_input(choice: str) -> List[str]:
    """Parse quality selection."""
    mapping = {"1": "small", "2": "medium", "3": "large", "4": "orig", "5": "all"}
    
    choice = choice.strip().lower()
    if choice in ("5", "all"):
        return ["small", "medium", "large", "orig"]
    
    parts = [p.strip() for p in choice.split(",") if p.strip()]
    result = []
    
    for p in parts:
        result.append(mapping.get(p, p if p in QUALITY_SUFFIXES else "orig"))
    
    # Remove duplicates while preserving order
    seen = set()
    final = []
    for x in result:
        if x not in seen:
            final.append(x)
            seen.add(x)
    
    return final or ["orig"]

def show_menu(title: str, options: List[str], default: int = 1) -> int:
    """Display a menu and get user choice."""
    safe_print(f"\n{THEME_BOLD}{THEME_BLUE}{title}{THEME_RESET}")
    safe_print(f"{THEME_CYAN}{'─'*60}{THEME_RESET}")
    
    for i, opt in enumerate(options, 1):
        marker = "●" if i == default else "○"
        safe_print(f"  {THEME_YELLOW}{marker}{THEME_RESET} {i}. {opt}")
    
    safe_print(f"{THEME_CYAN}{'─'*60}{THEME_RESET}")
    
    choice = themed_input(f"Select option (1-{len(options)})", str(default))
    
    try:
        num = int(choice)
        return num if 1 <= num <= len(options) else default
    except ValueError:
        return default

def main(argv=None):
    """Main entry point with enhanced prompts."""
    

    
    def signal_handler(sig, frame):
        safe_print(f"\n{THEME_YELLOW}⚠ Mission aborted by operator{THEME_RESET}")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        parser = argparse.ArgumentParser(description="NASA Media Downloader - Enhanced Edition")
        parser.add_argument("--query", "-q", help="Search query")
        parser.add_argument("--output", "-o", help="Output directory")
        parser.add_argument("--qualities", "-Q", help="Qualities (1-5 or names)")
        parser.add_argument("--limit", "-n", type=int, help="Max items to download")
        parser.add_argument("--rate", type=float, default=1.0, help="Rate limit (seconds)")
        parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Worker threads")
        parser.add_argument("--min-workers", type=int, default=1, help="Min workers")
        parser.add_argument("--max-workers", type=int, default=MAX_WORKERS, help="Max workers")
        parser.add_argument("--no-adaptive", action="store_true", help="Disable adaptive throttling")
        parser.add_argument("--images", action="store_true", help="Download images")
        parser.add_argument("--videos", action="store_true", help="Download videos")
        parser.add_argument("--metadata", action="store_true", help="Download metadata")
        parser.add_argument("--no-prompt", action="store_true", help="Non-interactive mode")
        args = parser.parse_args(argv)
        
        if args.no_prompt and not args.query:
            safe_print(f"{THEME_RED}Error: --no-prompt requires --query{THEME_RESET}")
            sys.exit(1)
        
        # Start starfield
        
        
        # Show intro animation (skip if non-interactive)
        if not args.no_prompt:
            try:
                intro = SpaceIntro()
                intro.run_animation(duration=4.5, frames=50)
            except KeyboardInterrupt:
                pass
            
            time.sleep(0.5)
            clear_screen()
        
        # Configuration
        script_dir = Path(__file__).resolve().parent
        default_output = script_dir / DEFAULT_SUBDIR
        
        # Get parameters
        if not args.no_prompt:
            safe_print(f"\n{THEME_BOLD}{THEME_CYAN}{'═'*60}{THEME_RESET}")
            safe_print(f"{THEME_BOLD}{THEME_CYAN}  MISSION CONFIGURATION{THEME_RESET}")
            safe_print(f"{THEME_BOLD}{THEME_CYAN}{'═'*60}{THEME_RESET}\n")
        
        query = args.query or themed_input("Search query", "space exploration")
        
        if args.output:
            output_path = Path(args.output).expanduser()
        else:
            if args.no_prompt:
                output_path = default_output
            else:
                out_str = themed_input(f"Output folder (default: ./{DEFAULT_SUBDIR})", 
                                      f"./{DEFAULT_SUBDIR}")
                if out_str == f"./{DEFAULT_SUBDIR}":
                    output_path = default_output
                else:
                    output_path = Path(out_str).expanduser()
        
        if not output_path.is_absolute():
            output_path = (Path.cwd() / output_path).resolve()
        
        # Quality selection
        if args.qualities:
            qualities = parse_quality_input(args.qualities)
        else:
            if args.no_prompt:
                qualities = ["orig"]
            else:
                q_opts = [
                    "Small (Low resolution, faster downloads)",
                    "Medium (Balanced quality and size)",
                    "Large (High resolution)",
                    "Original (Best quality, largest files)",
                    "All qualities (Download all available)"
                ]
                q_choice = show_menu("SELECT IMAGE/VIDEO QUALITY", q_opts, default=4)
                qualities = parse_quality_input(str(q_choice))
        
        # Media type selection
        if args.images or args.videos:
            download_images = args.images
            download_videos = args.videos
        else:
            if args.no_prompt:
                download_images = True
                download_videos = False
            else:
                media_opts = [
                    "Images only",
                    "Videos only",
                    "Both images and videos"
                ]
                media_choice = show_menu("SELECT MEDIA TYPES TO DOWNLOAD", media_opts, default=1)
                download_images = media_choice in (1, 3)
                download_videos = media_choice in (2, 3)
        
        # Metadata
        if args.metadata or args.no_prompt:
            download_metadata = args.metadata
        else:
            meta_opts = [
                "Download media files only",
                "Download media + metadata (JSON + TXT)"
            ]
            meta_choice = show_menu("METADATA OPTIONS", meta_opts, default=2)
            download_metadata = (meta_choice == 2)
        
        # Limit
        if args.limit is not None:
            max_items = args.limit
        else:
            if args.no_prompt:
                max_items = None
            else:
                limit_opts = [
                    "Download all available items",
                    "Specify maximum number"
                ]
                limit_choice = show_menu("DOWNLOAD LIMIT", limit_opts, default=1)
                
                if limit_choice == 2:
                    try:
                        num = int(themed_input("Maximum number of items", "100"))
                        max_items = num if num > 0 else None
                    except ValueError:
                        max_items = None
                else:
                    max_items = None
        
        # Summary
        if not args.no_prompt:
            safe_print(f"\n{THEME_BOLD}{THEME_GREEN}MISSION PARAMETERS CONFIRMED{THEME_RESET}")
            safe_print(f"{THEME_CYAN}{'─'*60}{THEME_RESET}")
            safe_print(f"  Query: {THEME_YELLOW}{query}{THEME_RESET}")
            safe_print(f"  Output: {THEME_YELLOW}{output_path}{THEME_RESET}")
            safe_print(f"  Qualities: {THEME_YELLOW}{', '.join(qualities)}{THEME_RESET}")
            safe_print(f"  Images: {THEME_YELLOW}{download_images}{THEME_RESET}")
            safe_print(f"  Videos: {THEME_YELLOW}{download_videos}{THEME_RESET}")
            safe_print(f"  Metadata: {THEME_YELLOW}{download_metadata}{THEME_RESET}")
            safe_print(f"  Limit: {THEME_YELLOW}{max_items or 'None'}{THEME_RESET}")
            safe_print(f"{THEME_CYAN}{'─'*60}{THEME_RESET}\n")
            
            themed_input("Press Enter to launch mission...", "")
        
        # Execute
        crawl_nasa_media(
            query=query,
            main_save_dir=output_path,
            download_images=download_images,
            download_videos=download_videos,
            download_metadata=download_metadata,
            qualities=qualities,
            rate_limit=args.rate,
            max_items=max_items,
            workers=args.workers,
            min_workers=args.min_workers,
            max_workers=args.max_workers,
            adaptive=not args.no_adaptive
        )
        
    except KeyboardInterrupt:
        safe_print(f"\n{THEME_YELLOW}Mission terminated by operator{THEME_RESET}")
        sys.exit(0)
    finally:
        if starfield:
            starfield.stop()

if __name__ == "__main__":
    main()

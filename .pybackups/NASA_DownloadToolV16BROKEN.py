#!/usr/bin/env python3
"""
NASA Image Download Tool - Polished Themed Release (live stats & bandwidth test)

Table of Contents (use as a map while reading the file)
1.  INTRO & CONFIGURATION ..................... (CONFIG)
2.  THEME / TERMINAL HELPERS .................. (THEME)
3.  PERSISTENT STARFIELD ...................... (STARFIELD)
4.  GALAXY ZOOM INTRO ANIMATION ............... (INTRO)
5.  NETWORK SESSIONS & HTTP HELPERS ........... (NETWORK)
6.  ADAPTIVE CONTROLLER ........................ (ADAPTIVE)
7.  NASA API WRAPPER .......................... (API)
8.  DOWNLOAD HELPERS .......................... (DOWNLOAD)
9.  ESTIMATION / PRE-SCAN LOGIC ................ (ESTIMATE)
10. LIVE STATS MONITOR ........................ (MONITOR)
11. ORCHESTRATION / CRAWL LOGIC ............... (CRAWL)
12. CLI, PROMPTS, MISSION MANIFEST & RUN ...... (CLI)

Purpose:
- Single-file themed downloader for NASA Images API with pre-scan estimates,
  bandwidth detection, adaptive concurrency, and a live telemetry dashboard
  showing detailed stats while downloading.
- Requires: requests, tqdm
"""

from __future__ import annotations

# ------------------------
# CONFIG & IMPORTS
# ------------------------
import argparse
import concurrent.futures
import collections
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

# Config
DEFAULT_SUBDIR = "NASA-Downloads"
LOG_SUBDIR = "logs"
LOG_FILENAME = "nasa_downloader.log"
API_SEARCH_URL = "https://images-api.nasa.gov/search"
API_ASSET_URL = "https://images-api.nasa.gov/asset"
QUALITY_SUFFIXES = {"small": "~small", "medium": "~medium", "large": "~large", "orig": "~orig"}
THEME_TITLE = "NASA IMAGE DOWNLOADER — MISSION DECK"
THEME_PROMPT_PREFIX = "\x1b[36mCOMMAND DECK>\x1b[0m"
THEME_INPUT_PROMPT = "\x1b[33mCAPTAIN>\x1b[0m"
THEME_INFO = "\x1b[32m"
THEME_WARN = "\x1b[33m"
THEME_ERROR = "\x1b[31m"
THEME_RESET = "\x1b[0m"
STARFIELD_ROWS = 4
STARFIELD_DENSITY = 0.045
STARFIELD_INTERVAL = 0.6
DEFAULT_WORKERS = 6
MAX_WORKERS = 12
DEFAULT_RATE = 1.0
RETRY_TOTAL = 3
RETRY_BACKOFF = 0.5
# default fallback bandwidth (bytes/sec)
DEFAULT_BANDWIDTH_BYTES_PER_SEC = 2_000_000

random.seed()

# ------------------------
# THEME / TERMINAL HELPERS
# ------------------------
def enable_ansi_on_windows():
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            new_mode = mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
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
        return max(40, size.columns), max(10, size.lines)
    except Exception:
        return 80, 24

def safe_print(s: str = "", end: str = "\n"):
    sys.stdout.write(s + end)
    sys.stdout.flush()

def themed_input(prompt: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    sys.stdout.write(f"\n{THEME_PROMPT_PREFIX} {prompt}{hint}\n{THEME_INPUT_PROMPT} ")
    sys.stdout.flush()
    try:
        val = input().strip()
    except EOFError:
        val = ""
    return val if val else default

# ------------------------
# STARFIELD
# ------------------------
class Starfield:
    def __init__(self, rows: int = STARFIELD_ROWS, density: float = STARFIELD_DENSITY, interval: float = STARFIELD_INTERVAL):
        self.rows = max(1, int(rows))
        self.density = float(density)
        self.interval = max(0.05, float(interval))
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._cols, _ = get_terminal_size()
        self._palette = [".", "*", "+", "·", "✦", "✶"]
        self._stars: List[Tuple[int, int, str]] = []
        self._init_stars()

    def _init_stars(self):
        cols, _ = get_terminal_size()
        self._cols = cols
        approx_cells = int(self._cols * self.rows)
        star_count = max(6, int(approx_cells * self.density))
        coords = set()
        while len(coords) < star_count:
            r = random.randrange(0, self.rows)
            c = random.randrange(0, self._cols)
            coords.add((r, c))
        self._stars = [(r, c, random.choice(self._palette)) for (r, c) in coords]

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 1.0):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run(self):
        enable_ansi_on_windows()
        hide_cursor()
        try:
            while not self._stop.is_set():
                cols, _ = get_terminal_size()
                if cols != self._cols:
                    with self._lock:
                        self._cols = cols
                        self._init_stars()
                updated = []
                for (r, c, ch) in self._stars:
                    if random.random() < 0.14:
                        ch = random.choice(self._palette)
                    if random.random() < 0.04:
                        c = max(0, min(self._cols - 1, c + random.randint(-1, 1)))
                        r = max(0, min(self.rows - 1, r + random.randint(-1, 1)))
                    updated.append((r, c, ch))
                with self._lock:
                    self._stars = updated
                canvas = [[" " for _ in range(self._cols)] for __ in range(self.rows)]
                with self._lock:
                    for (r, c, ch) in self._stars:
                        if 0 <= r < self.rows and 0 <= c < self._cols:
                            canvas[r][c] = ch
                try:
                    sys.stdout.write("\x1b[s")
                    sys.stdout.write("\x1b[H")
                    for row in canvas:
                        line = "".join(row)
                        sys.stdout.write(line.ljust(self._cols) + "\n")
                    sys.stdout.write("\x1b[u")
                    sys.stdout.flush()
                except Exception:
                    pass
                time.sleep(self.interval)
        finally:
            show_cursor()

# ------------------------
# GALAXY INTRO
# ------------------------
PALETTE_INTENSITY = [" ", ".", ":", "-", "=", "+", "*", "O", "0", "@", "#"]

def map_intensity_to_char(val: float) -> str:
    idx = int(max(0.0, min(0.9999, val)) * len(PALETTE_INTENSITY))
    return PALETTE_INTENSITY[idx]

def generate_galaxy_particles(n: int = 1200, arms: int = 4, randomness: float = 0.6):
    particles = []
    max_theta = 6.0 * math.pi
    for i in range(n):
        t = random.random()
        theta = t * max_theta
        arm = i % arms
        arm_offset = (arm / arms) * (2 * math.pi)
        r = 0.5 * (theta / max_theta) ** 0.8 * 3.0
        spin = 1.5
        angle = theta * spin + arm_offset
        r *= 1.0 + (random.random() - 0.5) * randomness
        angle += (random.random() - 0.5) * 0.6 * randomness
        x = r * math.cos(angle)
        y = r * math.sin(angle)
        intensity = max(0.05, 1.0 - (r / 3.5) + (random.random() - 0.5) * 0.2)
        particles.append((x, y, intensity))
    for _ in range(max(60, n // 20)):
        x = (random.random() - 0.5) * 0.3
        y = (random.random() - 0.5) * 0.3
        intensity = 1.0 - random.random() * 0.3
        particles.append((x, y, intensity))
    random.shuffle(particles)
    return particles

def render_frame(particles: List[Tuple[float, float, float]], cols: int, rows: int, scale: float, cx: float = 0.0, cy: float = 0.0):
    W, H = cols, rows
    buffer = [[0.0 for _ in range(W)] for __ in range(H)]
    cx_term = W // 2
    cy_term = H // 2
    for (x, y, intensity) in particles:
        px = int(cx_term + (x - cx) * scale)
        py = int(cy_term + (y - cy) * scale * 0.5)
        if 0 <= px < W and 0 <= py < H:
            buffer[py][px] = min(1.0, buffer[py][px] + intensity)
            for dx, dy, w in ((1, 0, 0.25), (-1, 0, 0.25), (0, 1, 0.25), (0, -1, 0.25)):
                nx, ny = px + dx, py + dy
                if 0 <= nx < W and 0 <= ny < H:
                    buffer[ny][nx] = min(1.0, buffer[ny][nx] + intensity * w)
    lines = []
    for row in buffer:
        line = "".join(map_intensity_to_char(v) for v in row)
        lines.append(line)
    return "\n".join(lines)

def galaxy_zoom_animation(duration: float = 3.5, frames: int = 40):
    enable_ansi_on_windows()
    term_w, term_h = get_terminal_size()
    cols = min(120, term_w)
    rows = min(40, term_h - 6)
    if rows < 8 or cols < 40:
        return
    hide_cursor()
    try:
        particles = generate_galaxy_particles(n=1100, arms=4, randomness=0.65)
        t0 = time.time()
        for i in range(frames):
            t = i / max(1, frames - 1)
            if t < 0.15:
                interp = t / 0.15
                scale = lerp(18.0, 7.0, interp)
            elif t < 0.85:
                interp = (t - 0.15) / 0.7
                scale = lerp(7.0, 2.4, interp)
            else:
                interp = (t - 0.85) / 0.15
                scale = lerp(2.4, 0.9, interp)
            wobble = math.sin(t * 6.28 * 1.4) * 0.02
            cx = wobble * (1 - t) * 1.5
            cy = math.cos(t * 3.14 * 1.7) * 0.02 * (1 - t)
            if random.random() < 0.04:
                idx = random.randrange(len(particles))
                x, y, val = particles[idx]
                particles[idx] = (x, y, min(1.0, val + 0.6))
            frame_s = render_frame(particles, cols, rows, scale, cx, cy)
            clear_screen()
            header = (" " + THEME_TITLE + " ").center(term_w)
            safe_print("\n" + header + "\n")
            left_pad = max(0, (term_w - cols) // 2)
            pad = " " * left_pad
            safe_print("\n".join(pad + line for line in frame_s.splitlines()))
            footer = ("Tip: Press Ctrl+C to cancel at any time").center(term_w)
            safe_print("\n" + footer)
            elapsed = time.time() - t0
            target = (i + 1) * (duration / max(1, frames))
            sleep_for = max(0.0, target - elapsed)
            time.sleep(sleep_for)
    finally:
        show_cursor()

def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

# ------------------------
# NETWORK / SESSIONS
# ------------------------
_thread_local = threading.local()

def make_session(pool_maxsize: int = 10, retries: int = RETRY_TOTAL, backoff_factor: float = RETRY_BACKOFF) -> requests.Session:
    s = requests.Session()
    retry = Retry(total=retries, backoff_factor=backoff_factor, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset(["HEAD", "GET", "OPTIONS"]))
    adapter = HTTPAdapter(pool_connections=pool_maxsize, pool_maxsize=pool_maxsize, max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({"User-Agent": "nasa-image-downloader/1.0"})
    return s

def get_thread_session(pool_maxsize: int = 10, retries: int = RETRY_TOTAL, backoff_factor: float = RETRY_BACKOFF) -> requests.Session:
    if not hasattr(_thread_local, "session"):
        _thread_local.session = make_session(pool_maxsize=pool_maxsize, retries=retries, backoff_factor=backoff_factor)
    return _thread_local.session

# ------------------------
# ADAPTIVE CONTROLLER
# ------------------------
class AdaptiveController:
    def __init__(self, min_workers: int = 1, max_workers: int = MAX_WORKERS):
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
            self.success = self.fail = self.throttle = self.total = 0
        new_workers = current_workers
        cooldown = 0.0
        if thr_rate > 0.08:
            new_workers = max(self.min_workers, int(current_workers * 0.5))
            cooldown = min(60, 5 + int(thr_rate * 200))
            logging.getLogger().warning("High throttle rate %.1f%% -> reducing workers to %s, cooldown %ss", thr_rate * 100, new_workers, cooldown)
            return new_workers, cooldown
        if fail_rate > 0.25:
            new_workers = max(self.min_workers, int(current_workers * 0.7))
            cooldown = min(30, 3 + int(fail_rate * 40))
            logging.getLogger().warning("High failure rate %.1f%% -> reducing workers to %s, cooldown %ss", fail_rate * 100, new_workers, cooldown)
            return new_workers, cooldown
        if succ_rate > 0.95 and current_workers < self.max_workers:
            new_workers = min(self.max_workers, current_workers + 1)
            logging.getLogger().info("High success rate %.1f%% -> increasing workers to %s", succ_rate * 100, new_workers)
            return new_workers, 0.0
        return new_workers, cooldown

# ------------------------
# NASA API WRAPPER
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

    def search_raw(self, query: str, page: int = 1, media_type: str = "image"):
        try:
            resp = self.session.get(API_SEARCH_URL, params={"q": query, "media_type": media_type, "page": page}, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return {}

    def search(self, query: str, page: int = 1, media_type: str = "image") -> Tuple[List[NasaItem], bool]:
        try:
            payload = self.search_raw(query, page=page, media_type=media_type)
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
                    raw=d))
            more = len(items) > 0
            return results, more
        except Exception as e:
            logging.getLogger().error("Search failed for page %s: %s", page, e)
            return [], False

    def get_total_hits(self, query: str) -> Optional[int]:
        payload = self.search_raw(query, page=1)
        try:
            th = payload.get("collection", {}).get("metadata", {}).get("total_hits")
            if isinstance(th, int):
                return th
        except Exception:
            pass
        return None

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

# ------------------------
# DOWNLOAD HELPERS
# ------------------------
def sanitize_filename(s: str, max_len: int = 120) -> str:
    if not s:
        return "item"
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

# ------------------------
# LIVE STATS MONITOR (MONITOR)
# ------------------------
class DownloadStatsMonitor:
    """
    Tracks global statistics and renders a live telemetry panel beneath the starfield.
    - Tracks files queued, completed, successes, failures, bytes transferred.
    - Computes short-term throughput (sliding window).
    - Shows ETA based on remaining bytes and measured throughput.
    """

    def __init__(self, header_rows: int = STARFIELD_ROWS, panel_height: int = 7, update_interval: float = 0.6):
        self.header_rows = header_rows
        self.panel_height = panel_height
        self.update_interval = update_interval
        self._lock = threading.Lock()
        self._start_time = None
        self.total_files_est = None
        self.queued = 0
        self.completed = 0
        self.success = 0
        self.failed = 0
        self.bytes_downloaded = 0
        self._recent = collections.deque()  # (timestamp, bytes)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.current_workers = DEFAULT_WORKERS
        self.active_tasks = 0
        self.last_update = time.time()

    def start(self):
        with self._lock:
            self._start_time = time.time()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 1.0):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def set_total_files_est(self, n: Optional[int]):
        with self._lock:
            self.total_files_est = n

    def set_workers(self, n: int):
        with self._lock:
            self.current_workers = n

    def add_queued(self, n: int = 1):
        with self._lock:
            self.queued += n

    def start_task(self):
        with self._lock:
            self.active_tasks += 1

    def end_task(self, success: bool, bytes_count: int):
        with self._lock:
            self.active_tasks = max(0, self.active_tasks - 1)
            self.completed += 1
            if success:
                self.success += 1
            else:
                self.failed += 1
            self.bytes_downloaded += bytes_count
            self._recent.append((time.time(), bytes_count))
            self.last_update = time.time()

    def add_bytes(self, n: int):
        with self._lock:
            self.bytes_downloaded += n
            self._recent.append((time.time(), n))
            self.last_update = time.time()

    def _throughput(self, window: float = 6.0) -> float:
        cutoff = time.time() - window
        s = 0
        with self._lock:
            # drop old
            while self._recent and self._recent[0][0] < cutoff:
                self._recent.popleft()
            for t, b in self._recent:
                s += b
        return s / window if window > 0 else 0.0

    def _render_panel(self):
        cols, lines = get_terminal_size()
        # prepare lines
        with self._lock:
            elapsed = time.time() - (self._start_time or time.time())
            done = self.completed
            succ = self.success
            fail = self.failed
            active = self.active_tasks
            queued = max(0, self.queued - done)
            bytes_d = self.bytes_downloaded
            est_files = self.total_files_est
            throughput = self._throughput()
            avg_speed = throughput
        # estimate remaining bytes if est_files known and avg file size known from bytes_d/done
        avg_file = (bytes_d / done) if done else 0
        if est_files and est_files > done:
            rem_files = est_files - done
            est_rem_bytes = rem_files * avg_file
            eta_seconds = est_rem_bytes / avg_speed if avg_speed > 0 else None
        else:
            rem_files = None
            est_rem_bytes = None
            eta_seconds = None

        # Build ASCII bars and info
        def bar(percent, width=30):
            filled = int(width * percent)
            return "[" + "#" * filled + "-" * (width - filled) + "]"

        percent_done = (done / est_files) if (est_files and est_files > 0) else 0.0
        pbar = bar(percent_done, width=min(40, cols - 40))
        lines_out = []
        lines_out.append(THEME_INFO + " TELEMETRY " + THEME_RESET + " | Live Mission Stats")
        lines_out.append(f" Workers: {self.current_workers}   Active: {active}   Queued items: {queued}")
        lines_out.append(f" Completed: {done} (OK:{succ} ERR:{fail})   Estimated total items: {est_files or 'unknown'}")
        lines_out.append(f" Progress: {pbar} {percent_done*100:5.1f}%")
        lines_out.append(f" Downloaded: {format_bytes(bytes_d)}   Speed: {format_bytes(avg_speed)}/s")
        lines_out.append(f" Avg file size: {format_bytes(avg_file) if avg_file else 'unknown'}")
        if eta_seconds is not None:
            lines_out.append(f" ETA: {format_seconds(eta_seconds)}   Elapsed: {format_seconds(elapsed)}")
        else:
            lines_out.append(f" ETA: unknown   Elapsed: {format_seconds(elapsed)}")
        # Pad to panel_height
        while len(lines_out) < self.panel_height:
            lines_out.append("")

        # render without disturbing cursor
        try:
            sys.stdout.write("\x1b[s")  # save cursor
            # move to row = header_rows + 1
            sys.stdout.write(f"\x1b[{self.header_rows + 1};1H")
            for ln in lines_out:
                sys.stdout.write(ln.ljust(cols)[:cols] + "\n")
            sys.stdout.write("\x1b[u")  # restore cursor
            sys.stdout.flush()
        except Exception:
            pass

    def _run(self):
        while not self._stop.is_set():
            self._render_panel()
            time.sleep(self.update_interval)

    def start_background(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

# ------------------------
# ESTIMATE helpers & bandwidth test
# ------------------------
def format_bytes(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024.0:
            return f"{num:3.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"

def format_seconds(sec: float) -> str:
    sec = int(round(sec))
    if sec < 60:
        return f"{sec}s"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"

def bandwidth_test(url: str, bytes_to_fetch: int = 200_000, timeout: float = 10.0) -> Optional[float]:
    """
    Try a ranged GET (if supported) to measure throughput quickly.
    Returns bytes/sec or None on failure.
    """
    session = make_session(pool_maxsize=2, retries=0, backoff_factor=0.1)
    headers = {"Range": f"bytes=0-{bytes_to_fetch-1}"}
    try:
        t0 = time.time()
        r = session.get(url, headers=headers, stream=True, timeout=timeout)
        r.raise_for_status()
        total = 0
        for chunk in r.iter_content(chunk_size=32_768):
            if not chunk:
                break
            total += len(chunk)
            if total >= bytes_to_fetch:
                break
        t1 = time.time()
        dur = max(1e-6, t1 - t0)
        return total / dur if total > 0 else None
    except Exception:
        return None

# ------------------------
# ESTIMATION / PRE-SCAN
# ------------------------
def estimate_download_plan(api: NasaAPI, query: str, qualities: List[str], sample_size: int = 5, bandwidth_bytes_per_sec: int = DEFAULT_BANDWIDTH_BYTES_PER_SEC):
    info = {
        "total_hits": None,
        "est_items": None,
        "avg_files_per_item": None,
        "est_total_files": None,
        "avg_file_bytes": None,
        "est_total_bytes": None,
        "est_seconds": None,
        "measured_bandwidth": None,
    }
    total_hits = api.get_total_hits(query)
    if total_hits and isinstance(total_hits, int):
        info["total_hits"] = total_hits
        info["est_items"] = total_hits
    else:
        items, _ = api.search(query=query, page=1)
        info["est_items"] = len(items)
    sample_items, _ = api.search(query=query, page=1)
    sample_items = sample_items[:sample_size]
    if not sample_items:
        info.update({"avg_files_per_item": 0, "avg_file_bytes": 0, "est_total_files": 0, "est_total_bytes": 0, "est_seconds": 0})
        return info
    total_files = 0
    total_bytes = 0
    counted_files_for_size = 0
    head_session = make_session(pool_maxsize=4, retries=1, backoff_factor=0.2)
    sample_asset_for_bw = None
    for item in sample_items:
        nasa_id = item.nasa_id
        urls = api.get_asset_urls(nasa_id)
        matched = []
        if urls:
            for q in qualities:
                suff = QUALITY_SUFFIXES.get(q, "")
                found = [u for u in urls if suff in u.lower()]
                if found:
                    matched.extend(found)
                else:
                    c = construct_quality_url(nasa_id, q)
                    if c:
                        matched.append(c)
        else:
            for q in qualities:
                c = construct_quality_url(nasa_id, q)
                if c:
                    matched.append(c)
        matched = list(dict.fromkeys(matched))
        total_files += len(matched)
        for u in matched[:3]:
            if sample_asset_for_bw is None:
                sample_asset_for_bw = u
            try:
                h = head_session.head(u, timeout=8, allow_redirects=True)
                size = int(h.headers.get("content-length") or 0)
                if size > 0:
                    total_bytes += size
                    counted_files_for_size += 1
            except Exception:
                continue
    avg_files = total_files / max(1, len(sample_items))
    avg_bytes = (total_bytes / max(1, counted_files_for_size)) if counted_files_for_size else 0
    est_items = info["est_items"] or len(sample_items)
    est_total_files = int(round(est_items * avg_files))
    est_total_bytes = int(round(est_total_files * avg_bytes))
    # attempt bandwidth measurement from a sample asset if available
    measured_bw = None
    if sample_asset_for_bw:
        measured_bw = bandwidth_test(sample_asset_for_bw, bytes_to_fetch=150_000, timeout=8)
    bw = measured_bw or bandwidth_bytes_per_sec
    est_seconds = est_total_bytes / float(bw) if bw and est_total_bytes else 0
    info.update({
        "avg_files_per_item": avg_files,
        "avg_file_bytes": avg_bytes,
        "est_total_files": est_total_files,
        "est_total_bytes": est_total_bytes,
        "est_seconds": est_seconds,
        "measured_bandwidth": measured_bw,
    })
    return info

# ------------------------
# download tasks (integrate monitor)
# ------------------------
def _download_task(url: str, dest: Path, controller: Optional[AdaptiveController], monitor: Optional["DownloadStatsMonitor"], chunk_size: int = 65536, retries: int = 3) -> bool:
    session = get_thread_session(pool_maxsize=10, retries=max(1, retries), backoff_factor=0.5)
    if monitor:
        monitor.start_task()
    bytes_written = 0
    try:
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
                                bytes_written += len(chunk)
                                if monitor:
                                    monitor.add_bytes(len(chunk))
                if controller:
                    controller.report("success")
                return True
            except requests.RequestException as exc:
                logging.getLogger().warning("Attempt %s failed for %s: %s", attempt, url, exc)
                time.sleep(min(10, 0.5 * (2 ** attempt)))
            except Exception as exc:
                logging.getLogger().warning("Attempt %s error for %s: %s", attempt, url, exc)
                time.sleep(min(10, 0.5 * (2 ** attempt)))
        if controller:
            controller.report("fail")
        return False
    finally:
        if monitor:
            monitor.end_task(success=(bytes_written > 0), bytes_count=bytes_written)

def download_urls_concurrent(url_dest_pairs: List[Tuple[str, Path]], workers: int = DEFAULT_WORKERS, controller: Optional[AdaptiveController] = None, monitor: Optional["DownloadStatsMonitor"] = None) -> int:
    success_count = 0
    if not url_dest_pairs:
        return 0
    total = len(url_dest_pairs)
    if monitor:
        monitor.add_queued(total)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as exe:
        futures = [exe.submit(_download_task, url, dest, controller, monitor) for url, dest in url_dest_pairs]
        for fut in tqdm(concurrent.futures.as_completed(futures), total=total, desc="Downloading", unit="file"):
            try:
                ok = fut.result()
                if ok:
                    success_count += 1
            except Exception as exc:
                logging.getLogger().exception("Download task raised: %s", exc)
    return success_count

# ------------------------
# ORCHESTRATION / CRAWL
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

def write_mission_manifest(search_dir: Path, manifest: Dict):
    try:
        search_dir.mkdir(parents=True, exist_ok=True)
        mf = search_dir / "mission_manifest.json"
        with open(mf, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)
        logging.getLogger().info("Mission manifest written to %s", mf)
    except Exception as exc:
        logging.getLogger().warning("Failed to write mission manifest: %s", exc)

def crawl_nasa_images(
    query: str,
    main_save_dir: Path,
    download_images: bool,
    download_metadata: bool,
    qualities: List[str],
    rate_limit: float = DEFAULT_RATE,
    max_images: Optional[int] = None,
    workers: int = DEFAULT_WORKERS,
    min_workers: int = 1,
    max_workers: int = MAX_WORKERS,
    adaptive: bool = True,
    session: Optional[requests.Session] = None,
):
    top_session = session or make_session(pool_maxsize=max(4, workers // 2), retries=RETRY_TOTAL, backoff_factor=RETRY_BACKOFF)
    api = NasaAPI(session=top_session)
    main_save_dir = ensure_writable_dir(main_save_dir)
    sanitized_query = sanitize_filename(query) or "search"
    search_dir = main_save_dir / sanitized_query
    search_dir = ensure_writable_dir(search_dir)
    configure_logging(search_dir)
    manifest = {
        "query": query,
        "qualities": qualities,
        "download_images": download_images,
        "download_metadata": download_metadata,
        "workers": workers,
        "adaptive": adaptive,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_mission_manifest(search_dir, manifest)
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

    # Create monitor and start background rendering
    monitor = DownloadStatsMonitor(header_rows=STARFIELD_ROWS, panel_height=8, update_interval=0.8)
    monitor.start_background()
    # set estimated total if available
    try:
        total_hits = api.get_total_hits(query)
        monitor.set_total_files_est(total_hits)
    except Exception:
        pass
    monitor.set_workers(workers)

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
                    total_downloaded += download_urls_concurrent(page_url_dest_pairs, workers=current_workers, controller=controller, monitor=monitor)
                print_summary(total_downloaded, total_metadata)
                monitor.stop()
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
                safe_print(f"{THEME_INFO}Queued{THEME_RESET} {filename_base}: {title}")
            file_counter += 1
            time.sleep(rate_limit)
        if download_images and page_url_dest_pairs:
            monitor.set_workers(current_workers)
            total_downloaded += download_urls_concurrent(page_url_dest_pairs, workers=current_workers, controller=controller, monitor=monitor)
        if adaptive and controller:
            new_workers, cooldown = controller.evaluate_and_adjust(current_workers)
            if new_workers != current_workers:
                logging.getLogger().info("Adjusting worker count %s -> %s", current_workers, new_workers)
                current_workers = new_workers
                monitor.set_workers(current_workers)
            if cooldown and cooldown > 0:
                logging.getLogger().warning("Sleeping for %s seconds due to throttling/failures.", cooldown)
                time.sleep(cooldown)
        page += 1
        if not more:
            break
    print_summary(total_downloaded, total_metadata)
    monitor.stop()

def print_summary(total_downloaded: int, total_metadata: int) -> None:
    safe_print("\n" + THEME_INFO + "=== Mission Summary ===" + THEME_RESET)
    safe_print(f"Total images downloaded: {total_downloaded}")
    safe_print(f"Total metadata files saved: {total_metadata}")
    safe_print(THEME_INFO + "================" + THEME_RESET)

# ------------------------
# CLI & RUN
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

# small helper for HEAD session reuse
def head_size(url: str) -> int:
    try:
        s = make_session(pool_maxsize=2, retries=1)
        r = s.head(url, timeout=8, allow_redirects=True)
        r.raise_for_status()
        return int(r.headers.get("content-length") or 0)
    except Exception:
        return 0

def main(argv=None):
    starfield: Optional[Starfield] = None
    try:
        parser = argparse.ArgumentParser(description="NASA Image Download Tool (polished)")
        parser.add_argument("--query", "-q", help="Search query (default interactive)", default=None)
        parser.add_argument("--output", "-o", help="Root output folder (default: script_folder/NASA-Downloads)", default=None)
        parser.add_argument("--qualities", "-Q", help="Qualities (1..5 or names, comma-separated). Default orig.", default=None)
        parser.add_argument("--limit", "-n", type=int, help="Max images to download (default: all)", default=None)
        parser.add_argument("--rate", type=float, help="Delay between processing items/pages in seconds (default 1.0)", default=DEFAULT_RATE)
        parser.add_argument("--workers", type=int, help=f"Initial concurrent download worker threads (default {DEFAULT_WORKERS}, max {MAX_WORKERS})", default=DEFAULT_WORKERS)
        parser.add_argument("--min-workers", type=int, help="Minimum allowed workers when adapting (default 1)", default=1)
        parser.add_argument("--max-workers", type=int, help="Maximum allowed workers when adapting (default 12)", default=MAX_WORKERS)
        parser.add_argument("--no-adaptive", action="store_true", help="Disable adaptive throttling")
        parser.add_argument("--images", action="store_true", help="Download images")
        parser.add_argument("--metadata", action="store_true", help="Download metadata (JSON + TXT)")
        parser.add_argument("--no-prompt", action="store_true", help="Do not prompt interactively; requires --query")
        args = parser.parse_args(argv)

        if args.no_prompt and not args.query:
            safe_print(THEME_ERROR + "Error: --no-prompt requires --query to be set." + THEME_RESET)
            sys.exit(2)

        initial_workers = max(1, min(MAX_WORKERS, int(args.workers or DEFAULT_WORKERS)))
        min_workers = max(1, int(args.min_workers or 1))
        max_workers = max(min_workers, int(args.max_workers or MAX_WORKERS))
        if max_workers > 32:
            max_workers = 32

        # start starfield
        starfield = Starfield(rows=STARFIELD_ROWS, density=STARFIELD_DENSITY, interval=STARFIELD_INTERVAL)
        starfield.start()

        # intro if interactive
        if not args.no_prompt:
            try:
                galaxy_zoom_animation(duration=3.5, frames=42)
            except KeyboardInterrupt:
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
            safe_print("\n" + "\x1b[35mWhat do you want to download?\x1b[0m")
            safe_print("  1 - Images only")
            safe_print("  2 - Images and metadata")
            safe_print("  3 - Metadata only")
            choice = themed_input("Enter 1, 2, or 3 (default 2):", "2")
            download_images = choice in ("1", "2")
            download_metadata = choice in ("2", "3")

        # Determine how many images to download:
        if args.limit is not None:
            max_images = args.limit
        else:
            safe_print("\n" + "\x1b[35mHow many images do you want to download?\x1b[0m")
            safe_print("  1 - All available images")
            safe_print("  2 - Specify number")
            amt = themed_input("Enter 1 or 2 (default 1):", "1")
            if amt == "2":
                try:
                    v = int(themed_input("Enter the maximum number of images to download:", "0"))
                    max_images = v if v > 0 else None
                except Exception:
                    max_images = None
            else:
                max_images = None

        # Pre-scan estimate when "All"
        if max_images is None and download_images:
            api = NasaAPI(session=make_session(pool_maxsize=4))
            safe_print(THEME_INFO + "\nScanning repository for an estimate..." + THEME_RESET)
            try:
                info = estimate_download_plan(api, query, qualities, sample_size=6, bandwidth_bytes_per_sec=DEFAULT_BANDWIDTH_BYTES_PER_SEC)
                total_items = info.get("total_hits") or info.get("est_items") or 0
                avg_files = info.get("avg_files_per_item") or 0
                est_files = info.get("est_total_files") or 0
                avg_size = info.get("avg_file_bytes") or 0
                est_bytes = info.get("est_total_bytes") or 0
                est_seconds = info.get("est_seconds") or 0
                measured_bw = info.get("measured_bandwidth")
                safe_print(f"  Estimated items matching query: {total_items}")
                safe_print(f"  Estimated files to download (avg {avg_files:.2f} files/item): {est_files}")
                if measured_bw:
                    safe_print(f"  Measured bandwidth: {format_bytes(measured_bw)}/s (used for ETA)")
                else:
                    safe_print(f"  Using default assumed bandwidth: {format_bytes(DEFAULT_BANDWIDTH_BYTES_PER_SEC)}/s")
                safe_print(f"  Estimated total download size: {format_bytes(est_bytes)} (avg file {format_bytes(avg_size)})")
                safe_print(f"  Estimated download time: {format_seconds(est_seconds)}")
                proceed = themed_input("Proceed to download ALL with these estimates? (y/N):", "n").lower() in ("y", "yes")
                if not proceed:
                    try:
                        v = int(themed_input("Enter the maximum number of images to download (or 0 to cancel):", "0"))
                        if v <= 0:
                            safe_print(THEME_WARN + "Download canceled by user." + THEME_RESET)
                            return
                        max_images = v
                    except Exception:
                        safe_print(THEME_WARN + "Invalid number, canceling." + THEME_RESET)
                        return
                else:
                    max_images = None
            except Exception as exc:
                logging.getLogger().warning("Failed to estimate downloads: %s", exc)
                proceed = themed_input("Could not estimate. Proceed to download ALL anyway? (y/N):", "n").lower() in ("y", "yes")
                if not proceed:
                    try:
                        v = int(themed_input("Enter the maximum number of images to download (or 0 to cancel):", "0"))
                        if v <= 0:
                            safe_print(THEME_WARN + "Download canceled by user." + THEME_RESET)
                            return
                        max_images = v
                    except Exception:
                        safe_print(THEME_WARN + "Invalid number, canceling." + THEME_RESET)
                        return
                else:
                    max_images = None

        try:
            rate_limit = float(themed_input("Enter delay between requests in seconds (default 1.0):", str(args.rate or DEFAULT_RATE)))
        except Exception:
            rate_limit = args.rate or DEFAULT_RATE

        adaptive = not args.no_adaptive

        safe_print("\n" + THEME_INFO + "Initializing mission parameters..." + THEME_RESET)
        safe_print(f"  Query: {query}")
        safe_print(f"  Output root: {output_path}")
        safe_print(f"  Qualities: {qualities}")
        safe_print(f"  Download images: {download_images} | Download metadata: {download_metadata}")
        safe_print(f"  Workers: {initial_workers} (adaptive: {adaptive})\n")

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
        safe_print("\n" + THEME_ERROR + "Interrupted by user. Exiting." + THEME_RESET)
        sys.exit(1)
    finally:
        if 'starfield' in locals() and starfield is not None:
            try:
                starfield.stop()
            except Exception:
                pass

if __name__ == "__main__":
    main()
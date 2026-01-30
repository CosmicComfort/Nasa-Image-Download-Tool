"""
Enhanced starfield animation with twinkling stars and shooting stars.
"""

import random
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple

from .terminal import (
    enable_ansi_on_windows,
    get_terminal_size,
    hide_cursor,
    show_cursor,
)


class EnhancedStarfield:
    """Enhanced starfield with twinkling stars and shooting stars."""

    def __init__(self, rows: int = 5, density: float = 0.05, interval: float = 0.5):
        """
        Initialize the starfield.

        Args:
            rows: Number of rows for the starfield
            density: Star density (0.0 to 1.0)
            interval: Animation interval in seconds
        """
        self.rows = max(1, rows)
        self.density = density
        self.interval = interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._cols, _ = get_terminal_size()
        self._palette = [".", "·", "*", "✦", "✶", "⋆", "✧"]
        self._stars: List[Tuple[int, int, str, float]] = []  # r, c, char, brightness
        self._shooting_stars: List[Dict] = []
        self._init_stars()

    def _init_stars(self) -> None:
        """Initialize star positions and properties."""
        cols, _ = get_terminal_size()
        self._cols = cols
        star_count = max(10, int(self._cols * self.rows * self.density))
        coords = set()

        while len(coords) < star_count:
            r = random.randrange(0, self.rows)
            c = random.randrange(0, self._cols)
            coords.add((r, c))

        self._stars = [
            (r, c, random.choice(self._palette), random.random())
            for (r, c) in coords
        ]

    def _add_shooting_star(self) -> None:
        """Potentially add a new shooting star."""
        if len(self._shooting_stars) < 2 and random.random() < 0.02:
            self._shooting_stars.append({
                "x": random.randrange(0, self._cols),
                "y": 0,
                "vx": random.uniform(2, 4),
                "vy": random.uniform(0.5, 1.5),
                "trail": ["─", "╌", "·"],
            })

    def start(self) -> None:
        """Start the starfield animation in a background thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 1.0) -> None:
        """
        Stop the starfield animation.

        Args:
            timeout: Maximum time to wait for thread to stop
        """
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _update_stars(self) -> None:
        """Update star brightness and characters."""
        updated = []
        for (r, c, ch, brightness) in self._stars:
            # Randomly vary brightness
            if random.random() < 0.1:
                brightness = max(0.1, min(1.0, brightness + random.uniform(-0.3, 0.3)))

            # Select character based on brightness
            if brightness > 0.8:
                ch = random.choice(self._palette[-3:])
            elif brightness > 0.5:
                ch = random.choice(self._palette[2:5])
            else:
                ch = random.choice(self._palette[:3])

            updated.append((r, c, ch, brightness))

        self._stars = updated

    def _update_shooting_stars(self) -> None:
        """Update shooting star positions."""
        active = []
        for ss in self._shooting_stars:
            ss["x"] += ss["vx"]
            ss["y"] += ss["vy"]
            if ss["x"] < self._cols and ss["y"] < self.rows:
                active.append(ss)
        self._shooting_stars = active

    def _render(self) -> None:
        """Render the starfield to the terminal."""
        # Create canvas
        canvas = [[" " for _ in range(self._cols)] for _ in range(self.rows)]

        # Draw stars
        for (r, c, ch, _) in self._stars:
            if 0 <= r < self.rows and 0 <= c < self._cols:
                canvas[r][c] = ch

        # Draw shooting stars with trails
        for ss in self._shooting_stars:
            x, y = int(ss["x"]), int(ss["y"])
            for i, trail_char in enumerate(ss["trail"]):
                tx = int(x - i * ss["vx"] * 0.3)
                ty = int(y - i * ss["vy"] * 0.3)
                if 0 <= ty < self.rows and 0 <= tx < self._cols:
                    canvas[ty][tx] = trail_char

        # Output to terminal
        try:
            sys.stdout.write("\x1b[s\x1b[H")  # Save cursor, move to home
            for row in canvas:
                sys.stdout.write("".join(row).ljust(self._cols) + "\n")
            sys.stdout.write("\x1b[u")  # Restore cursor
            sys.stdout.flush()
        except Exception:
            pass

    def _run(self) -> None:
        """Main animation loop."""
        enable_ansi_on_windows()
        hide_cursor()

        try:
            while not self._stop.is_set():
                # Check for terminal resize
                cols, _ = get_terminal_size()
                if cols != self._cols:
                    self._cols = cols
                    self._init_stars()

                # Update and render
                self._update_stars()
                self._add_shooting_star()
                self._update_shooting_stars()
                self._render()

                time.sleep(self.interval)
        finally:
            show_cursor()

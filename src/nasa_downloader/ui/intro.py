"""
Space intro animation with galaxy, nebula, and UFO.
"""

import math
import random
import time
from typing import List, Tuple

from .terminal import (
    clear_screen,
    enable_ansi_on_windows,
    get_terminal_size,
    hide_cursor,
    safe_print,
    show_cursor,
)
from .themes import Theme


class SpaceIntro:
    """Procedurally generated space scene with galaxy, nebula, and UFO."""

    def __init__(self):
        self.palette_stars = [" ", ".", "·", ":", "*", "⋆", "✦",]
        self.palette_nebula = [" ", ".", ":", "~", "≈", "▒", "▓", "█"]
        self.palette_galaxy = [" ", ".", "·", ":", "*", "+", "○", "●"]

    @staticmethod
    def lerp(a: float, b: float, t: float) -> float:
        """Linear interpolation between two values."""
        return a + (b - a) * t

    def generate_galaxy_particles(
        self, n: int = 1500, arms: int = 5
    ) -> List[Tuple[float, float, float]]:
        """
        Generate spiral galaxy particles.

        Args:
            n: Number of particles
            arms: Number of spiral arms

        Returns:
            List of (x, y, intensity) tuples
        """
        particles = []
        max_theta = 7.0 * math.pi

        for i in range(n):
            t = random.random()
            theta = t * max_theta
            arm = i % arms
            arm_offset = (arm / arms) * (2 * math.pi)

            r = 0.45 * (theta / max_theta) ** 0.75 * 3.5
            spin = 1.8
            angle = theta * spin + arm_offset

            # Add randomness
            r *= 1.0 + (random.random() - 0.5) * 0.7
            angle += (random.random() - 0.5) * 0.5

            x = r * math.cos(angle)
            y = r * math.sin(angle)

            intensity = max(0.05, 1.0 - (r / 4.0) + (random.random() - 0.5) * 0.3)
            particles.append((x, y, intensity))

        # Add bright core
        for _ in range(n // 15):
            x = (random.random() - 0.5) * 0.25
            y = (random.random() - 0.5) * 0.25
            intensity = 1.0 - random.random() * 0.2
            particles.append((x, y, intensity))

        return particles

    def generate_nebula(self, cols: int, rows: int) -> List[List[float]]:
        """
        Generate nebula using Perlin-like noise.

        Args:
            cols: Number of columns
            rows: Number of rows

        Returns:
            2D array of intensity values
        """
        nebula = [[0.0 for _ in range(cols)] for _ in range(rows)]

        # Multiple octaves of noise
        for octave in range(4):
            freq = 2**octave
            amp = 1.0 / (2**octave)

            for y in range(rows):
                for x in range(cols):
                    nx = x / cols * freq
                    ny = y / rows * freq

                    # Simple pseudo-noise
                    val = (
                        math.sin(nx * 3.7 + ny * 2.1)
                        + math.cos(nx * 1.9 - ny * 4.3)
                        + math.sin((nx + ny) * 2.8)
                    ) / 3.0
                    val = (val + 1.0) / 2.0

                    nebula[y][x] += val * amp

        # Normalize
        max_val = max(max(row) for row in nebula)
        if max_val > 0:
            for y in range(rows):
                for x in range(cols):
                    nebula[y][x] = (nebula[y][x] / max_val) * 0.4

        return nebula

    def draw_ufo(
        self, canvas: List[List[str]], x: int, y: int, frame: int
    ) -> None:
        """
        Draw a UFO with animation.

        Args:
            canvas: 2D character canvas
            x: X position
            y: Y position
            frame: Current animation frame
        """
        ufo_frames = [
            [
                "    ╭───╮    ",
                "   ╱ ◉ ◉ ╲   ",
                "  ╱───────╲  ",
                " ▔▔▔▔▔▔▔▔▔▔ ",
            ],
            [
                "    ╭───╮    ",
                "   ╱ ◉ ◉ ╲   ",
                "  ╱───────╲  ",
                " ▁▁▁▁▁▁▁▁▁▁ ",
            ],
        ]

        ufo = ufo_frames[frame % 2]
        h, w = len(canvas), len(canvas[0]) if canvas else 0

        for dy, line in enumerate(ufo):
            py = y + dy
            if 0 <= py < h:
                for dx, ch in enumerate(line):
                    px = x + dx - len(line) // 2
                    if 0 <= px < w and ch != " ":
                        canvas[py][px] = ch

    def render_frame(
        self,
        particles: List[Tuple[float, float, float]],
        nebula: List[List[float]],
        cols: int,
        rows: int,
        scale: float,
        cx: float,
        cy: float,
        show_ufo: bool,
        frame: int,
    ) -> str:
        """
        Render complete frame with galaxy, nebula, and UFO.

        Args:
            particles: Galaxy particle list
            nebula: Nebula intensity grid
            cols: Terminal columns
            rows: Terminal rows
            scale: Zoom scale
            cx, cy: Camera offset
            show_ufo: Whether to show UFO
            frame: Current frame number

        Returns:
            Rendered frame as string
        """
        W, H = cols, rows
        buffer = [[0.0 for _ in range(W)] for _ in range(H)]

        # Add nebula layer
        for y in range(min(H, len(nebula))):
            for x in range(min(W, len(nebula[0]))):
                buffer[y][x] = nebula[y][x] * 0.3

        # Add galaxy particles
        cx_term = W // 2
        cy_term = H // 2

        for px, py, intensity in particles:
            x = int(cx_term + (px - cx) * scale)
            y = int(cy_term + (py - cy) * scale * 0.5)

            if 0 <= x < W and 0 <= y < H:
                buffer[y][x] = min(1.0, buffer[y][x] + intensity * 0.8)

                # Glow effect
                for dx, dy_offset, weight in [
                    (1, 0, 0.3),
                    (-1, 0, 0.3),
                    (0, 1, 0.3),
                    (0, -1, 0.3),
                ]:
                    nx, ny = x + dx, y + dy_offset
                    if 0 <= nx < W and 0 <= ny < H:
                        buffer[ny][nx] = min(1.0, buffer[ny][nx] + intensity * weight)

        # Convert to characters
        canvas = []
        for row in buffer:
            line = []
            for val in row:
                if val > 0.7:
                    char = random.choice(self.palette_galaxy[-3:])
                elif val > 0.4:
                    char = random.choice(self.palette_galaxy[4:7])
                elif val > 0.15:
                    char = random.choice(self.palette_galaxy[2:5])
                else:
                    char = (
                        self.palette_galaxy[0]
                        if val < 0.05
                        else self.palette_galaxy[1]
                    )
                line.append(char)
            canvas.append(line)

        # Draw UFO
        if show_ufo:
            ufo_x = W // 2 + int(math.sin(frame * 0.1) * 15)
            ufo_y = H // 4
            self.draw_ufo(canvas, ufo_x, ufo_y, frame)

        return "\n".join("".join(row) for row in canvas)

    def run_animation(self, duration: float = 4.5, frames: int = 50) -> None:
        """
        Run the space intro animation.

        Args:
            duration: Total animation duration in seconds
            frames: Number of frames to render
        """
        enable_ansi_on_windows()
        term_w, term_h = get_terminal_size()
        cols = min(140, term_w)
        rows = min(45, term_h - 8)

        if rows < 10 or cols < 50:
            return

        hide_cursor()
        try:
            # Generate content
            particles = self.generate_galaxy_particles(n=1400, arms=5)
            nebula = self.generate_nebula(cols, rows)

            t0 = time.time()
            for i in range(frames):
                t = i / max(1, frames - 1)

                # Zoom phases
                if t < 0.12:
                    interp = t / 0.12
                    scale = self.lerp(25.0, 9.0, interp)
                    show_ufo = False
                elif t < 0.75:
                    interp = (t - 0.12) / 0.63
                    scale = self.lerp(9.0, 2.8, interp)
                    show_ufo = t > 0.3
                else:
                    interp = (t - 0.75) / 0.25
                    scale = self.lerp(2.8, 1.2, interp)
                    show_ufo = True

                # Camera movement
                wobble = math.sin(t * 6.28 * 1.2) * 0.015
                cx = wobble * (1 - t) * 2.0
                cy = math.cos(t * 3.14 * 1.5) * 0.015 * (1 - t)

                # Random star flicker
                if random.random() < 0.05:
                    idx = random.randrange(len(particles))
                    x, y, val = particles[idx]
                    particles[idx] = (x, y, min(1.0, val + 0.5))

                # Render
                frame_str = self.render_frame(
                    particles, nebula, cols, rows, scale, cx, cy, show_ufo, i
                )

                clear_screen()

                # Title
                title = f"{Theme.BOLD}{Theme.CYAN}╔═══════════════════════════════════════════════════════╗{Theme.RESET}"
                subtitle = f"{Theme.BOLD}{Theme.CYAN}║  NASA MEDIA DOWNLOADER — DEEP SPACE MISSION CONTROL  ║{Theme.RESET}"
                footer = f"{Theme.BOLD}{Theme.CYAN}╚═══════════════════════════════════════════════════════╝{Theme.RESET}"

                safe_print("\n" + title.center(term_w))
                safe_print(subtitle.center(term_w))
                safe_print(footer.center(term_w) + "\n")

                left_pad = max(0, (term_w - cols) // 2)
                pad = " " * left_pad
                safe_print("\n".join(pad + line for line in frame_str.splitlines()))

                tip = f"{Theme.YELLOW}⚡ Initializing quantum entanglement protocols... {int(t * 100)}%{Theme.RESET}"
                safe_print("\n" + tip.center(term_w))

                elapsed = time.time() - t0
                target = (i + 1) * (duration / max(1, frames))
                time.sleep(max(0.0, target - elapsed))

        finally:
            show_cursor()

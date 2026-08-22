#!/usr/bin/env python3
"""
CUPID AGENTS terminal demo

Features:
- Animated pixel/particle terminal intro
- Pixel text art: "CUPID AGENTS"
- Interactive prompt like a lightweight coding-agent terminal
- Words starting with @ become grey
- Words starting with / become dark blue
- On Enter, shows animated "working" spinner for 2 seconds
- Replies: "task received!"

Run:
    pip install prompt_toolkit
    python cupid_agents_terminal.py
"""

import asyncio
import math
import os
import random
import shutil
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.lexers import Lexer
    from prompt_toolkit.styles import Style
except ImportError:
    print("Missing dependency: prompt_toolkit")
    print("Install it with:")
    print("  pip install prompt_toolkit")
    sys.exit(1)


# =========================
# Terminal helpers
# =========================

RESET = "\033[0m"
CLEAR = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

GOLD = "\033[38;2;255;204;92m"
DIM_GOLD = "\033[38;2;158;122;39m"
CREAM = "\033[38;2;255;243;210m"
GREY = "\033[38;2;130;130;130m"
DARK_BLUE = "\033[38;2;40;80;160m"
DIM = "\033[2m"


def clear_screen() -> None:
    print(CLEAR, end="", flush=True)


def terminal_size() -> Tuple[int, int]:
    size = shutil.get_terminal_size(fallback=(100, 30))
    return size.columns, size.lines


def move_home() -> None:
    print("\033[H", end="")


# =========================
# Pixel font
# =========================

FONT: Dict[str, List[str]] = {
    "A": [
        "01110",
        "10001",
        "10001",
        "11111",
        "10001",
        "10001",
        "10001",
    ],
    "C": [
        "01111",
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "01111",
    ],
    "D": [
        "11110",
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "11110",
    ],
    "E": [
        "11111",
        "10000",
        "10000",
        "11110",
        "10000",
        "10000",
        "11111",
    ],
    "G": [
        "01111",
        "10000",
        "10000",
        "10011",
        "10001",
        "10001",
        "01111",
    ],
    "I": [
        "11111",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
        "11111",
    ],
    "N": [
        "10001",
        "11001",
        "10101",
        "10011",
        "10001",
        "10001",
        "10001",
    ],
    "P": [
        "11110",
        "10001",
        "10001",
        "11110",
        "10000",
        "10000",
        "10000",
    ],
    "S": [
        "01111",
        "10000",
        "10000",
        "01110",
        "00001",
        "00001",
        "11110",
    ],
    "T": [
        "11111",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
    ],
    "U": [
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "01110",
    ],
    " ": [
        "000",
        "000",
        "000",
        "000",
        "000",
        "000",
        "000",
    ],
}


def text_to_pixels(text: str, scale_x: int = 2, scale_y: int = 1) -> List[Tuple[int, int]]:
    """
    Convert text into pixel coordinates.
    Coordinates are relative, not terminal-positioned yet.
    """
    pixels: List[Tuple[int, int]] = []
    cursor_x = 0

    for ch in text.upper():
        glyph = FONT.get(ch)
        if glyph is None:
            cursor_x += 6 * scale_x
            continue

        for y, row in enumerate(glyph):
            for x, bit in enumerate(row):
                if bit == "1":
                    for sy in range(scale_y):
                        for sx in range(scale_x):
                            pixels.append((cursor_x + x * scale_x + sx, y * scale_y + sy))

        cursor_x += (len(glyph[0]) + 1) * scale_x

    return pixels


@dataclass
class Particle:
    x: float
    y: float
    tx: float
    ty: float
    char: str


def make_particles_for_text(text: str) -> List[Particle]:
    cols, rows = terminal_size()
    raw_pixels = text_to_pixels(text, scale_x=2, scale_y=1)

    if not raw_pixels:
        return []

    max_x = max(p[0] for p in raw_pixels)
    max_y = max(p[1] for p in raw_pixels)

    offset_x = max(2, (cols - max_x) // 2)
    offset_y = max(3, (rows - max_y) // 3)

    particles: List[Particle] = []

    for px, py in raw_pixels:
        target_x = offset_x + px
        target_y = offset_y + py

        # Start particles from random edges, giving a "world forming" feel.
        edge = random.choice(["top", "bottom", "left", "right"])
        if edge == "top":
            start_x = random.uniform(0, cols - 1)
            start_y = random.uniform(0, 2)
        elif edge == "bottom":
            start_x = random.uniform(0, cols - 1)
            start_y = random.uniform(rows - 4, rows - 1)
        elif edge == "left":
            start_x = random.uniform(0, 3)
            start_y = random.uniform(0, rows - 1)
        else:
            start_x = random.uniform(cols - 4, cols - 1)
            start_y = random.uniform(0, rows - 1)

        particles.append(
            Particle(
                x=start_x,
                y=start_y,
                tx=target_x,
                ty=target_y,
                char=random.choice(["•", "·", "▪", "◆"]),
            )
        )

    return particles


def ease_out_cubic(t: float) -> float:
    return 1 - pow(1 - t, 3)


def render_particles(particles: List[Particle], progress: float, footer: str = "") -> str:
    cols, rows = terminal_size()
    canvas = [[" " for _ in range(cols)] for _ in range(rows)]

    # Small pixel "sky" background dots.
    random.seed(7)
    for _ in range(max(10, cols // 5)):
        x = random.randint(0, cols - 1)
        y = random.randint(0, max(0, rows // 2))
        if random.random() < 0.6:
            canvas[y][x] = "·"

    t = ease_out_cubic(progress)

    for p in particles:
        x = int(p.x + (p.tx - p.x) * t)
        y = int(p.y + (p.ty - p.y) * t)

        if 0 <= x < cols and 0 <= y < rows:
            canvas[y][x] = "█" if progress > 0.86 else p.char

    # Footer
    if footer:
        y = min(rows - 2, max(0, rows - 2))
        start_x = max(0, (cols - len(footer)) // 2)
        for i, ch in enumerate(footer[:cols]):
            if start_x + i < cols:
                canvas[y][start_x + i] = ch

    return "\n".join("".join(row).rstrip() for row in canvas)


async def animate_intro() -> None:
    clear_screen()
    print(HIDE_CURSOR, end="", flush=True)

    particles = make_particles_for_text("CUPID AGENTS")

    frames = 38
    for i in range(frames + 1):
        progress = i / frames
        move_home()
        footer = "agent terminal initializing..." if i < frames else "ready"
        frame = render_particles(particles, progress, footer=footer)
        color = GOLD if i > frames * 0.7 else DIM_GOLD
        print(color + frame + RESET, end="", flush=True)
        await asyncio.sleep(0.035)

    await asyncio.sleep(0.45)
    print(SHOW_CURSOR, end="", flush=True)
    clear_screen()

    print(GOLD + "CUPID AGENTS" + RESET)
    print(DIM + "Type a message. Use @word for grey mentions and /word for dark-blue commands." + RESET)
    print(DIM + "Examples: @file explain this  |  /plan build a demo" + RESET)
    print()


# =========================
# Interactive prompt styling
# =========================

class CupidLexer(Lexer):
    """
    Dynamic lexer for prompt_toolkit.

    It colors:
    - words beginning with @ as grey
    - words beginning with / as dark blue
    - everything else as default
    """

    def lex_document(self, document):
        def get_line(lineno: int):
            line = document.lines[lineno]
            fragments = []

            i = 0
            while i < len(line):
                ch = line[i]

                if ch.isspace():
                    start = i
                    while i < len(line) and line[i].isspace():
                        i += 1
                    fragments.append(("", line[start:i]))
                    continue

                start = i
                while i < len(line) and not line[i].isspace():
                    i += 1

                word = line[start:i]

                if word.startswith("@"):
                    fragments.append(("class:mention", word))
                elif word.startswith("/"):
                    fragments.append(("class:command", word))
                else:
                    fragments.append(("", word))

            return fragments

        return get_line


STYLE = Style.from_dict(
    {
        "prompt": "#9423a6 bold",
        "mention": "#473d40 bold",
        "command": "#391b85 bold",
    }
)


async def working_animation(seconds: float = 2.0) -> None:
    spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    start = time.time()
    idx = 0

    print(HIDE_CURSOR, end="", flush=True)

    while time.time() - start < seconds:
        icon = spinner[idx % len(spinner)]
        dots = "." * ((idx % 3) + 1)
        sys.stdout.write("\r" + GOLD + f"{icon} working{dots}   " + RESET)
        sys.stdout.flush()
        idx += 1
        await asyncio.sleep(0.08)

    sys.stdout.write("\r" + " " * 40 + "\r")
    sys.stdout.flush()
    print(SHOW_CURSOR, end="", flush=True)


async def interactive_loop() -> None:
    session = PromptSession(lexer=CupidLexer(), style=STYLE)

    while True:
        try:
            user_message = await session.prompt_async(
                HTML("<prompt>cupid</prompt> <prompt>›</prompt> ")
            )

            if not user_message.strip():
                continue

            if user_message.strip() in {"exit", "quit", "/exit", "/quit"}:
                print(GREY + "Goodbye from CUPID AGENTS." + RESET)
                break

            await working_animation(2.0)
            print(GOLD + "task received!" + RESET)
            print()

        except KeyboardInterrupt:
            print()
            print(GREY + "Interrupted. Type /quit to exit." + RESET)
        except EOFError:
            print()
            break


async def main() -> None:
    try:
        await animate_intro()
        await interactive_loop()
    finally:
        print(SHOW_CURSOR + RESET, end="", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

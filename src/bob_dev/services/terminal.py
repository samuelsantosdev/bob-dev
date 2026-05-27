"""terminal.py

Terminal output utilities for bob_dev:
  - ANSI color constants
  - Typed print helpers (error = red, success = green, plain for everything else)
  - Async spinner with ASCII desert-car animation
  - Async subprocess runner with the same animation
"""

from __future__ import annotations

import asyncio
import time
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# ANSI color codes
# ---------------------------------------------------------------------------

RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------

def print_error(msg: str) -> None:
    """Print a red error line prefixed with [✗]."""
    print(f"{RED}[✗] {msg}{RESET}")


def print_success(msg: str) -> None:
    """Print a green success line prefixed with [✓]."""
    print(f"{GREEN}[✓] {msg}{RESET}")


def print_info(msg: str) -> None:
    """Print a plain informational line (no colour)."""
    print(f"[i] {msg}")


def print_warn(msg: str) -> None:
    """Print a plain warning line (no colour)."""
    print(f"[!] {msg}")


def print_step(step: str, msg: str) -> None:
    """Print a bold step label (e.g. '[1/4]') followed by a plain message."""
    print(f"{BOLD}{step}{RESET} {msg}")


# ---------------------------------------------------------------------------
# ASCII desert-car animation helpers
# ---------------------------------------------------------------------------

# The landscape string is scrolled left one character per frame.
_DESERT = ". . ● . . o . . ● " * 2  # Repeated to ensure it's long enough for smooth scrolling
# Four frames of wheel animation for the car body.ƒ
_CAR_FRAMES = ["O", "O", "ᗧ", "ᗧ"]


def _render_car_frame(i: int, label: str, elapsed: float) -> str:
    """Build the single-line spinner string for frame index *i*."""
    offset    = i % len(_DESERT)
    landscape = (_DESERT[offset:] + _DESERT[:offset])[:6]
    car       = _CAR_FRAMES[i % len(_CAR_FRAMES)]
    return f"\r  {YELLOW}{car}{RESET} {landscape}(tokens) - {label}... ({elapsed:.1f}s)"


# ---------------------------------------------------------------------------
# Async spinner wrappers
# ---------------------------------------------------------------------------

async def run_with_spinner(func, *args, label: str = "Processing", **kwargs):
    """Run a blocking *func* in a thread while showing the car animation.

    Any extra *args* / *kwargs* are forwarded directly to *func*.
    The keyword argument *label* controls the text shown next to the animation
    and is consumed by this function (not forwarded).

    Returns whatever *func* returns.
    """
    # Schedule the blocking call without awaiting it immediately.
    task = asyncio.create_task(asyncio.to_thread(func, *args, **kwargs))

    start_time = time.time()
    i = 0
    while not task.done():
        elapsed = time.time() - start_time
        print(_render_car_frame(i, label, elapsed), end="", flush=True)
        i += 1
        await asyncio.sleep(0.12)

    # Clear the animation line.
    print("\r" + " " * 70 + "\r", end="", flush=True)
    return task.result()


async def run_subprocess(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run *cmd* as an async subprocess under *cwd* with the car animation.

    Streams stdout and stderr to the terminal once the process finishes.

    Returns:
        (returncode, stdout, stderr)
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    start_time = time.time()
    i = 0
    while proc.returncode is None:
        elapsed = time.time() - start_time
        print(_render_car_frame(i, "Running claude", elapsed), end="", flush=True)
        i += 1
        await asyncio.sleep(0.12)

    # Clear the animation line.
    print("\r" + " " * 70 + "\r", end="", flush=True)

    stdout, stderr = await proc.communicate()
    if stdout:
        print(stdout.decode())
    if stderr:
        print(stderr.decode())

    return proc.returncode, stdout.decode(), stderr.decode()

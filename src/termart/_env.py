# termart — Private environment helpers.

# Thin module that centralises the few things we need from the OS / terminal
# without scattering import os / ioctl noise across the public surface.
from __future__ import annotations

import os
import sys


def default_width() -> int:
    """Return a sensible default output width for the current environment.

    - Interactive TTY: terminal columns minus a small margin (min 40).
    - Non-TTY / piped / redirected: 100 (stable, predictable for scripts).
    """
    try:
        if hasattr(os, "get_terminal_size"):
            columns = os.get_terminal_size().columns
            if columns and columns > 0:
                return max(40, columns - 2)
    except Exception:
        pass
    # Fallback for non-TTY or when get_terminal_size is unavailable.
    if not sys.stdout.isatty():
        return 100
    return 80


def supports_truecolor() -> bool:
    """Delegate to color.supports_truecolor() so callers don't need to know
    which module owns that logic."""
    from .color import supports_truecolor as _stc
    return _stc()

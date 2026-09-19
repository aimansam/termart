# True-color and 256-color ANSI escape code helpers.

# We emit raw escape sequences ourselves (no dependency) because the codes are
# short and stable.  This module is the single place to tweak if a terminal
# quirk ever requires a workaround.

# Escape prefix — depends on the environment in theory, but \x1b is reliably
# correct for the platforms termart targets (Linux, macOS terminal emulators,
# Windows Terminal on modern Windows via VT processing).  We keep it explicit
# rather than importing os and re-deriving it on every call.
ESC = "\x1b"

# Reset – always emit at the end of a line (or before a new line) to prevent
# colour bleed across rows when the terminal wraps or when output is captured.
RESET = f"{ESC}[0m"

# Lower-level builders for the two true-color forms.
def fg_rgb(r: int, g: int, b: int) -> str:
    """Foreground true-color escape for (r, g, b) in 0-255 each."""
    return f"{ESC}[38;2;{r};{g};{b}m"


def bg_rgb(r: int, g: int, b: int) -> str:
    """Background true-color escape for (r, g, b) in 0-255 each."""
    return f"{ESC}[48;2;{r};{g};{b}m"


# 256-colour indexed forms (optional path, not the default).
def fg_256(index: int) -> str:
    return f"{ESC}[38;5;{index}m"


def bg_256(index: int) -> str:
    return f"{ESC}[48;5;{index}m"


# 256-colour palette index 0 = black, 7 = white, 16-231 = 6x6x6 colour cube,
# 232-255 = grayscale ramp.  The helpers below map an RGB triple to the nearest
# cube index (fast, not dithering) and to the nearest grayscale index.


def rgb_to_256_index(r: int, g: int, b: int) -> int:
    """Return the closest 256-colour cube/grayscale index for (r,g,b).

    Prefer the 6x6x6 colour cube (indices 16-231) when the colour is saturated
    enough; otherwise fall back to the grayscale ramp (232-255).  This is a
    fast nearest-neighbour choice, not a perceptual metric — adequate for a
    graceful degradation path, not for critical colour fidelity.
    """
    r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
    # Detect "near-gray": all channels within 28 of each other.
    if max(r, g, b) - min(r, g, b) <= 28:
        # Map to grayscale ramp: 232 + floor(avg/10), clamped to 255.
        avg = (r + g + b) // 3
        return 232 + min(23, avg // 10)

    # 6x6x6 cube: r,g,b each quantised to 0-5.
    ri = (r * 6) // 256
    gi = (g * 6) // 256
    bi = (b * 6) // 256
    return 16 + (36 * ri) + (6 * gi) + bi


# Capability probing / warnings.


def supports_truecolor(env: dict | None = None) -> bool:
    """Best-effort guess whether the terminal supports 24-bit true colour.

    Checks $COLORTERM (any value is treated as a positive signal by convention)
    and a small $TERM whitelist.  It is a heuristic, not a runtime probe —
    perfect accuracy would require an ioctl or a negotiation sequence which is
    out of scope for v1.
    """
    if env is None:
        import os
        env = os.environ
    colorterm = env.get("COLORTERM", "")
    if colorterm and colorterm.lower() in ("truecolor", "24bit"):
        return True
    term = env.get("TERM", "")
    # Known terminals that reliably support true colour.
    whitelisted = (
        "xterm-kitty", "xterm-256color",  # kitty advertises via COLORTERM, but be nice
        "tmux-256color", "tmux",  # tmux can pass truecolor if configured, but be conservative
        "alacritty", "alacritty-direct",
        "wezterm", "wezterm-direct",
        "foot", "foot-direct",
        "foot-special",
    )
    # We deliberately do NOT trust TERM alone for truecolor on tmux/xterm;
    # COLORTERM is the stronger signal.  Still, list a few safe ones.
    if term.lower() in whitelisted:
        return True
    return False


def emit_truecolor_warning() -> str:
    """Return a one-line warning (with reset) for terminals that are unlikely
    to support true colour.  The CLI may print this before rendering when
    colour is enabled but the environment looks suspect.
    """
    warning = (
        f"{ESC}[38;5;214m[termart] WARN: truecolor may not be supported "
        f"in this terminal. Results may be degraded. Use --no-color for "
        f"guaranteed monochrome output.{RESET}"
    )
    return warning

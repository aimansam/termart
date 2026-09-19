# Built-in character ramps for ASCII art modes.

# Each ramp is ordered from "densest" (darkest, used for low-brightness pixels)
# to "sparsest" (lightest, used for high-brightness pixels).
#
# Brightness is measured 0-255; a pixel's brightness value is mapped to an
# index in the ramp via: idx = int(brightness / 256 * len(ramp)) ranked so
# that 0 -> densest (dark) and 255 -> sparsest (light). The ramp string itself
# is dense-to-light, so the index is used directly from the left.

# Classic blockier ramp — the one most people picture for "ASCII art".
RAMP_CLASSIC = "@%#*+=-:. "

# Higher-resolution ramp with more steps — smoother gradients at the cost of
# "noisier" output when the source is low-contrast.
RAMP_DETAILED = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvun xrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^'. "

# A ramp tuned for pure block output (shade mode) — denser blocks first.
RAMP_SHADE = "█▓▒░ "

# Spaces-only ramp: useful for a "threshold" effect where only dark pixels
# get a mark.  Not a default anywhere, but available for custom use.
RAMP_DARK_ONLY = "@%#+=-:. "  # lighter chars still present for subtle gradients

# Space-terminated ramps are fine; some users prefer a trailing space so the
# brightest pixels render as empty (background).  Keep a couple of curated
# variants for convenience.

RAMP_CLASSIC_SPACED = "@%#*+=-:.  "  # double space at end for cleaner highlights

# Built-in set: name -> ramp string.  Used by the CLI `--chars` autocompletion
# and by library users who want a known ramp without typing it out.
BUILTIN_RAMPS = {
    "classic": RAMP_CLASSIC,
    "detailed": RAMP_DETAILED,
    "shade": RAMP_SHADE,
    "classic-spaced": RAMP_CLASSIC_SPACED,
    "dark-only": RAMP_DARK_ONLY,
    # Allow users to pass a ramp string directly; the CLI resolves a name first,
    # then treats the raw value as the ramp itself.
}


def brightness_to_char(brightness: int, ramp: str) -> str:
    """Map a 0-255 brightness value to a single character from *ramp*.

    The ramp is assumed to be ordered dense→light (darkest char first).  The
    brightest pixels map to the last character (typically a space) and the
    darkest to the first.
    """
    if not ramp:
        raise ValueError("ramp must not be empty")
    # Clamp brightness into [0, 255] defensively.
    b = max(0, min(255, int(brightness)))
    # Index: brighter pixel → higher index → lighter (later) character.
    idx = (b * (len(ramp) - 1)) // 255
    return ramp[idx]


def load_ramp(spec: str) -> str:
    """Resolve a ramp *spec* to an actual string.

    *spec* is first looked up in BUILTIN_RAMPS (case-insensitive).  If not
    found, the value itself is treated as the ramp string (so a user can pass
    ``"@%#*+=-:. "`` verbatim).  An empty string raises ValueError.
    """
    if not spec:
        raise ValueError("ramp must not be empty")
    lowered = spec.lower()
    if lowered in BUILTIN_RAMPS:
        return BUILTIN_RAMPS[lowered]
    # Treat as a raw ramp string.  Validate it has at least one non-space char
    # so we don't silently produce blank output.
    if not spec.strip():
        raise ValueError(f"ramp spec must contain at least one visible character, got {spec!r}")
    return spec

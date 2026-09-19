# Core rendering engine for termart.

# This is where the visual payoff lives.  Three rendering paths:
#   1. ASCII ranked-charset (monochrome or colour)
#   2. Half-block (two pixels per character, colour)
#   3. Shade blocks (block-based, colour-capable, lower resolution than half-block)
#
# Each path ultimately emits a plain string of ANSI escape codes — no printing
# happens inside this module.  The CLI / library layer owns I/O.
from __future__ import annotations

from typing import Literal

from . import charset, color, image

# Default mode names used by the CLI and the library API.
Mode = Literal["ascii", "halfblock", "shade"]

# When true colour is unavailable and a user hasn't opted into 256-colour
# explicitly, we fall back to monochrome so the output stays clean.  This is a
# deliberate v1 choice: 256-colour is available behind an opt-in flag later.
FALLBACK_TO_MONOCHROME_ON_NO_TRUECOLOR = True


def _emit_char(c: str, fg_ansi: str = "", bg_ansi: str = "", reset_after: bool = True) -> str:
    """Compose a single cell: optional fg, optional bg, the character, optional reset."""
    parts = []
    if fg_ansi:
        parts.append(fg_ansi)
    if bg_ansi:
        parts.append(bg_ansi)
    parts.append(c)
    if reset_after:
        parts.append(color.RESET)
    return "".join(parts)


def _cell_color(fg: tuple[int, int, int], bg: tuple[int, int, int],
                use_color: bool, invert: bool) -> tuple[str, str]:
    """Return (fg_ansi, bg_ansi) for a single cell given pixel colours.

    *invert*: when True, the foreground and background colours are swapped.
    This is used by the ``--invert`` flag, primarily meaningful for half-block
    mode (swap top/bottom pixel colour assignment).
    """
    if not use_color:
        return "", ""
    fg_r, fg_g, fg_b = fg
    bg_r, bg_g, bg_b = bg
    if invert:
        fg_r, fg_g, fg_b, bg_r, bg_g, bg_b = bg_r, bg_g, bg_b, fg_r, fg_g, fg_b
    return color.fg_rgb(fg_r, fg_g, fg_b), color.bg_rgb(bg_r, bg_g, bg_b)


# ---------------------------------------------------------------------------
# Brightness helpers (used by ASCII and shade modes)
# ---------------------------------------------------------------------------

def _rgb_brightness(r: int, g: int, b: int) -> int:
    """Perceived brightness (0-255) from an RGB triple.

    Uses a weighted luminance formula close to Rec. 601 luma, scaled into
    0-255.  The weighting is subjective but widely used for ASCII art.
    """
    # Clamp defensively.
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))
    # Standard luma coefficients.
    lum = (0.299 * r) + (0.587 * g) + (0.114 * b)
    return int(round(lum))


def _pixel_brightness(pixel: tuple[int, int, int] | tuple[int, int, int, int]) -> int:
    """Brightness from a pixel tuple, ignoring alpha if present."""
    if len(pixel) == 4:
        r, g, b, _ = pixel
        return _rgb_brightness(r, g, b)
    r, g, b = pixel[:3]
    return _rgb_brightness(r, g, b)


# ---------------------------------------------------------------------------
# Public render functions (library surface)
# ---------------------------------------------------------------------------

def render(image_source, *, mode: Mode = "halfblock", width: int | None = None,
           height: int | None = None, color_enabled: bool = True,
           invert: bool = False, chars: str | None = None,
           font_ratio: float = 2.0, scale_method: str = "lanczos",
           fit: str = "contain") -> str:
    """Render *image_source* to an ANSI string using *mode*.

    This is the primary library entry point.  It delegates to the mode-specific
    functions and resolves default sizing from the environment when *width* is
    not provided.
    """
    from .image import load_image, resize_image
    from . import _env

    img = load_image(image_source)

    if width is None:
        width = _env.default_width()

    # We pass *height* through as-is to resize_image; if None, it computes
    # from aspect ratio and font_ratio.
    resized = resize_image(img, width, height, font_ratio, scale_method)

    # Fit adjustment: if `fit` is not contain, apply post-hoc.
    if fit != "contain":
        resized = _apply_fit(resized, width, height, font_ratio, fit)

    if mode == "halfblock":
        return render_halfblock(resized, color_enabled=color_enabled,
                                invert=invert, font_ratio=font_ratio)
    elif mode == "ascii":
        return render_ascii(resized, color_enabled=color_enabled,
                            invert=invert, chars=chars)
    elif mode == "shade":
        return render_shade(resized, color_enabled=color_enabled,
                            invert=invert)
    else:
        raise ValueError(f"Unknown mode {mode!r}; choose from 'ascii', 'halfblock', 'shade'")


def render_halfblock(
    img: image.Image.Image,
    *,
    width: int = 80,
    color_enabled: bool = True,
    invert: bool = False,
    font_ratio: float = 2.0,
) -> str:
    """Render *img* in dual-pixel half-block mode (▄▀).

    For each pair of vertical pixel rows (top, bottom), we emit a single
    block character whose foreground colour = top pixel and background colour =
    bottom pixel (or vice-versa when *invert* is True for light backgrounds).

    Each output line corresponds to one row of block characters.  To render a
    full-height image we need twice as many pixel rows as output lines.

    *width* is the target output width in character columns.  The image is
    resized to fit within width × computed-height (aspect ratio × font_ratio)
    before rendering.
    """
    from .image import resize_image
    resized = resize_image(img, width, font_ratio=font_ratio)
    w, h = resized.size
    out_lines: list[list[str]] = [[] for _ in range(h)]

    for y in range(0, h, 2):
        for x in range(w):
            top_pixel = img.getpixel((x, y))
            if y + 1 < h:
                bottom_pixel = img.getpixel((x, y + 1))
            else:
                # Last row if height is odd: pair with black.
                bottom_pixel = (0, 0, 0)
            fg = _pixel_to_rgb(top_pixel)
            bg = _pixel_to_rgb(bottom_pixel)
            fg_ansi, bg_ansi = _cell_color(fg, bg, color_enabled, invert)
            out_lines[y // 2].append(_emit_char("▄" if not invert else "▀",
                                                  fg_ansi=fg_ansi, bg_ansi=bg_ansi))
        # Build newline for the finished row.
        # Note: we're appending to out_lines[y//2] inside the x-loop, which
        # means each row list accumulates one string per column.  We join below.
        pass

    # Rebuild: out_lines[y//2] already holds per-column strings.  Join.
    result_lines = []
    for row in out_lines:
        if row:
            result_lines.append("".join(row))
        else:
            result_lines.append("")
    return "\n".join(result_lines)


def render_ascii(
    img: image.Image.Image,
    *,
    width: int = 80,
    color_enabled: bool = True,
    invert: bool = False,
    chars: str | None = None,
) -> str:
    """Render *img* as ranked-charset ASCII art.

    Each pixel cell becomes one character.  Brightness is mapped to the ramp;
    if *color_enabled* is True, the character's foreground colour is the pixel
    colour (true colour or 256 fallback).  *chars* overrides the ramp (a string
    or a built-in name); when None we use the ``RAMP_CLASSIC`` default.

    Monochrome mode (color_enabled=False) returns char-only output with no ANSI
    codes.

    *width* is the target output width in character columns.  The image is
    resized to fit within width × computed-height (aspect ratio × font_ratio)
    before rendering.
    """
    from .image import resize_image
    resized = resize_image(img, width, font_ratio=2.0)
    ramp = chars
    if ramp is None:
        ramp = charset.RAMP_CLASSIC
    else:
        ramp = charset.load_ramp(ramp)

    w, h = resized.size
    out_lines: list[str] = []
    for y in range(h):
        row_chars: list[str] = []
        for x in range(w):
            pixel = img.getpixel((x, y))
            r, g, b = _pixel_to_rgb(pixel)
            bright = _rgb_brightness(r, g, b)
            ch = charset.brightness_to_char(bright, ramp)

            if color_enabled:
                fg_ansi, _ = _cell_color((r, g, b), (0, 0, 0), use_color=True, invert=invert)
                row_chars.append(_emit_char(ch, fg_ansi=fg_ansi, reset_after=True))
            else:
                row_chars.append(ch)
        out_lines.append("".join(row_chars))
    return "\n".join(out_lines)


def render_shade(
    img: image.Image.Image,
    *,
    width: int = 80,
    color_enabled: bool = True,
    invert: bool = False,
) -> str:
    """Render *img* using shade block characters (█▓▒░▄▀).

    Each pixel maps to a shade character by brightness.  This is the
    ``RAMP_SHADE`` ramp, which is far shorter than the ASCII ramp and produces
    a more "blocky" look with fewer distinct levels.  Colour works the same way
    as in ASCII mode (foreground colour = pixel colour).

    *width* is the target output width in character columns.  The image is
    resized to fit within width × computed-height (aspect ratio × font_ratio)
    before rendering.
    """
    from .image import resize_image
    resized = resize_image(img, width, font_ratio=2.0)
    ramp = charset.RAMP_SHADE
    w, h = resized.size
    out_lines: list[str] = []
    for y in range(h):
        row_chars: list[str] = []
        for x in range(w):
            pixel = img.getpixel((x, y))
            r, g, b = _pixel_to_rgb(pixel)
            bright = _rgb_brightness(r, g, b)
            ch = charset.brightness_to_char(bright, ramp)
            if color_enabled:
                fg_ansi, _ = _cell_color((r, g, b), (0, 0, 0), use_color=True, invert=invert)
                row_chars.append(_emit_char(ch, fg_ansi=fg_ansi, reset_after=True))
            else:
                row_chars.append(ch)
        out_lines.append("".join(row_chars))
    return "\n".join(out_lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _pixel_to_rgb(pixel: tuple) -> tuple[int, int, int]:
    """From a pixel tuple (may be 3- or 4-length) return (r,g,b)."""
    if len(pixel) == 4:
        return pixel[0], pixel[1], pixel[2]
    return pixel[0], pixel[1], pixel[2]


def _apply_fit(
    img: image.Image.Image,
    target_w: int,
    target_h: int | None,
    font_ratio: float,
    fit: str,
) -> image.Image.Image:
    """Post-hoc aspect adjustment for non-'contain' fit modes.

    For ``shrink``/``stretch``/``cover`` we resize the image to exactly the
    target dimensions (after font-ratio adjustment when target_h is None) and
    return it.  In contain mode we already did the right thing in resize_image.
    """
    if fit == "contain":
        return img

    src_w, src_h = img.size
    if target_h is None:
        aspect = src_w / src_h if src_h else 1.0
        target_h = max(1, round(target_w / aspect * font_ratio))

    method = image._resolve_resample("lanczos")  # default quality for fit ops
    if fit == "stretch":
        return img.resize((target_w, target_h), method)

    if fit == "cover":
        # Crop to cover the target (fill the box, crop overflow).
        src_ratio = src_w / src_h if src_h else 1.0
        tgt_ratio = target_w / target_h
        if src_ratio > tgt_ratio:
            # Source wider than target: crop width.
            new_w = round(target_w * (src_h / target_h))
            left = (src_w - new_w) // 2
            crop = img.crop((left, 0, left + new_w, src_h))
        else:
            # Source taller than target: crop height.
            new_h = round(target_h * (src_w / target_w))
            top = (src_h - new_h) // 2
            crop = img.crop((0, top, src_w, top + new_h))
        return crop.resize((target_w, target_h), method)

    if fit == "shrink":
        # Fit within the box without upscaling beyond source.
        if src_w <= target_w and src_h <= target_h:
            return img.copy()
        return _fit_resize_for_shrink(img, target_w, target_h, method)

    # Default: contain.
    return _fit_resize_for_contain(img, target_w, target_h, method)


def _fit_resize_for_shrink(img, max_w, max_h, method):
    """Contain-style fit but never upscale beyond source."""
    src_w, src_h = img.size
    if src_w <= max_w and src_h <= max_h:
        return img.copy()
    return image._fit_resize(img, max_w, max_h, method)


def _fit_resize_for_contain(img, max_w, max_h, method):
    """Same as image._fit_resize."""
    return image._fit_resize(img, max_w, max_h, method)


# ---------------------------------------------------------------------------
# TermArt configurator / context manager
# ---------------------------------------------------------------------------

class TermArt:
    """Configurator that produces render calls with preset options.

    Usage as a context manager is the most convenient pattern::

        with TermArt(mode="halfblock", width=120, color=True, font_ratio=2.0) as ctx:
            ansi = ctx.from_image(Image.open("photo.jpg"))

    You can also call the render methods directly without a context::

        ctx = TermArt(mode="ascii", width=80)
        ansi = ctx.from_path("photo.jpg")  # also loads from path
        print(ansi)
    """

    def __init__(
        self,
        *,
        mode: Mode = "halfblock",
        width: int | None = None,
        height: int | None = None,
        color: bool = True,
        invert: bool = False,
        chars: str | None = None,
        font_ratio: float = 2.0,
        scale_method: str = "lanczos",
        fit: str = "contain",
    ):
        self.mode = mode
        self.width = width
        self.height = height
        self.color = color
        self.invert = invert
        self.chars = chars
        self.font_ratio = font_ratio
        self.scale_method = scale_method
        self.fit = fit

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def from_path(self, path: str) -> str:
        """Render the image at *path* with this TermArt's config."""
        from .image import load_image
        img = load_image(path)
        return self.from_image(img)

    def from_image(self, img) -> str:
        """Render a PIL Image with this TermArt's config."""
        if self.width is None:
            from . import _env
            width = _env.default_width()
        else:
            width = self.width
        return render(
            img,
            mode=self.mode,
            width=width,
            height=self.height,
            color_enabled=self.color,
            invert=self.invert,
            chars=self.chars,
            font_ratio=self.font_ratio,
            scale_method=self.scale_method,
            fit=self.fit,
        )

    def from_bytes(self, data: bytes) -> str:
        """Render from raw image bytes (PNG, JPEG, etc.)."""
        from io import BytesIO
        from .image import load_image
        img = load_image(BytesIO(data))
        return self.from_image(img)


# ---------------------------------------------------------------------------
# Environment helpers (terminal width / truecolor probe)
# ---------------------------------------------------------------------------

# This submodule is imported lazily to avoid top-level ioctl/winsize noise.
_env = None


def _get_env():
    global _env
    if _env is None:
        from . import _env as env_mod
        _env = env_mod
    return _env


def _env_default_width():
    from . import _env as env_mod
    return env_mod.default_width()


# Convenience re-export so the CLI can call env helpers without importing a
# third module in multiple places.
default_width = _env_default_width

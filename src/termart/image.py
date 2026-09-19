# Image loading, conversion, and resize helpers for termart.

from __future__ import annotations

import os
from typing import BinaryIO, Union

from PIL import Image, ImageOps

# Acceptable input "images": a file path, a PIL Image, or a file-like object.
ImageLike = Union[str, Image.Image, BinaryIO]


def load_image(source: ImageLike) -> Image.Image:
    """Load *source* as an RGB PIL Image, converting non-RGB modes.

    - str → opened from path (clear error on missing/unreadable).
    - PIL.Image.Image → returned after ensuring RGB.
    - file-like (BinaryIO) → read by Pillow.
    """
    if isinstance(source, Image.Image):
        img = source
    elif isinstance(source, str):
        if not os.path.isfile(source):
            raise FileNotFoundError(f"Image file not found: {source}")
        try:
            img = Image.open(source)
        except Exception as exc:
            raise ValueError(f"Cannot read image {source!r}: {exc}") from exc
    else:
        # Assume file-like.
        try:
            img = Image.open(source)
        except Exception as exc:
            raise ValueError(f"Cannot read image from file-like object: {exc}") from exc

    return _to_rgb(img)


def _to_rgb(img: Image.Image) -> Image.Image:
    """Ensure *img* is RGB; convert common non-RGB modes in place where possible.

    - P (palette): convert directly to RGB.
    - L (grayscale): convert to RGB (1:1 mapping).
    - LA / RGBA / PA: drop alpha by compositing on black (default) — see
      _composite_alpha for the rationale.  We deliberately pick black because
      it keeps the ASCII/half-block mapping predictable: transparent areas
      become "dark" pixels.
    - CMYK: Pillow converts to RGB on .convert('RGB').
    """
    mode = img.mode
    if mode == "RGB":
        return img

    # Modes with alpha: composite on black.
    if mode in ("LA", "PA", "RGBA"):
        # Create a black background and composite.
        background = Image.new("RGB", img.size, (0, 0, 0))
        if mode in ("RGBA", "LA"):
            # Pillow's .convert('RGB') on RGBA does not composite — it just drops
            # alpha.  Use alpha_composite for correct treatment.
            rgb_img = img.convert("RGB")
            # For LA we converted to RGB but the alpha channel is lost — redo from
            # original.  Simpler: composite the RGBA/LA version.
            if mode == "RGBA":
                background.paste(rgb_img, mask=img.split()[-1])  # use alpha as mask
                return background
            # LA case: pilates-style.
            if mode == "LA":
                # LA → we can convert to RGBA via an intermediate to get alpha.
                rgba = img.convert("RGBA")
                background.paste(rgba.convert("RGB"), mask=rgba.split()[-1])
                return background
        return background

    if mode == "P":
        # Palette with no alpha → plain RGB.
        return img.convert("RGB")

    if mode == "L":
        return img.convert("RGB")

    # CMYK, etc. — Pillow can handle most in one shot.
    try:
        return img.convert("RGB")
    except Exception as exc:
        raise ValueError(f"Unsupported image mode {mode!r}; cannot convert to RGB: {exc}") from exc


def _composite_alpha(img: Image.Image, bg_color: tuple[int, int, int] = (0, 0, 0)) -> Image.Image:
    """Composite *img* (must have alpha) onto a solid background colour.

    Exposed for completeness / future --bg-color option.  The core pipeline
    uses black by default.
    """
    if img.mode not in ("RGBA", "LA", "PA"):
        return img.convert("RGB")
    background = Image.new("RGB", img.size, bg_color)
    if img.mode == "RGBA":
        background.paste(img.convert("RGB"), mask=img.split()[-1])
    else:
        # LA / PA → promote to RGBA first.
        rgba = img.convert("RGBA")
        background.paste(rgba.convert("RGB"), mask=rgba.split()[-1])
    return background


def resize_image(
    img: Image.Image,
    width: int,
    height: int | None = None,
    font_ratio: float = 2.0,
    scale_method: str = "lanczos",
) -> Image.Image:
    """Resize *img* to fit within *width* × *height* while preserving aspect.

    Behaviour:
    - *width* is the target terminal width in character columns.  Each column
      in half-block mode represents TWO pixel rows, so we compute output height
      from the image aspect ratio × *font_ratio* (default ~2.0) to counteract
      the typical terminal font being ~2× taller than wide.
    - If *height* is given, it caps the computed height; the image is fit
      within width×height using contain semantics (see _fit_resize).
    - If only *width* is given, height is computed as:
        height = round(width / (img.width / img.height) * font_ratio)
      then clamped to a sensible minimum of 1.
    - *scale_method* selects the Pillow resample filter:
        'nearest' → Image.NEAREST
        'bicubic' → Image.BICUBIC
        'lanczos' → Image.LANCZOS (default)
    - If the requested output is LARGER than the source on both dimensions,
      we do NOT upscale in v1 (to avoid blurry blown-up images).  The image is
      returned at its native size instead; the CLI warns when this happens.
    """
    if width < 1:
        raise ValueError(f"width must be >= 1, got {width}")
    if height is not None and height < 1:
        raise ValueError(f"height must be >= 1, got {height}")

    method = _resolve_resample(scale_method)

    src_w, src_h = img.size

    # Compute target height from aspect if not supplied.
    if height is None:
        aspect = src_w / src_h if src_h else 1.0
        height = max(1, round(width / aspect * font_ratio))

    # Upscale guard: if target exceeds source on BOTH axes, return original.
    if width > src_w and height > src_h:
        return img.copy()

    return _fit_resize(img, width, height, method)


def _fit_resize(
    img: Image.Image,
    max_width: int,
    max_height: int,
    method,
) -> Image.Image:
    """Fit *img* inside max_width × max_height preserving aspect (contain),
    then pad if necessary to exact dimensions.

    The returned image is exactly (max_width, max_height) pixels.  Padding is
    black (0,0,0), which matches the ASCII/half-block dark-pixel convention.
    """
    src_w, src_h = img.size
    ratio = min(max_width / src_w, max_height / src_h)
    new_w = max(1, round(src_w * ratio))
    new_h = max(1, round(src_h * ratio))

    resized = img.resize((new_w, new_h), method)

    # Pad to exact size if smaller (should only happen when the image is tiny).
    if new_w < max_width or new_h < max_height:
        padded = Image.new("RGB", (max_width, max_height), (0, 0, 0))
        padded.paste(resized, ((max_width - new_w) // 2, (max_height - new_h) // 2))
        return padded

    return resized


def _resolve_resample(method: str):
    """Map a method name to a Pillow resample constant."""
    table = {
        "nearest": Image.NEAREST,
        "bicubic": Image.BICUBIC,
        "lanczos": Image.LANCZOS,
    }
    key = method.lower()
    if key not in table:
        raise ValueError(
            f"Unknown scale method {method!r}; choose from {list(table.keys())}"
        )
    return table[key]

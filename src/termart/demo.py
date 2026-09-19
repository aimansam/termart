# Built-in demo image for `termart --demo`.

# The demo image is generated on the fly with Pillow — a colourful abstract
# composition that is instantly recognisable when rendered in half-block mode.
# This keeps the package small (no embedded base64 blob) while still giving a
# zero-setup, zero-download demo path.
#
# If you want to replace the demo image, subclass or monkeypatch
# ``get_demo_image`` at runtime, or file an issue / PR to make it configurable.
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter


def get_demo_image() -> Image.Image:
    """Return the built-in demo image as an RGB PIL Image (~160x100 px).

    The image is a colourful abstract composition: a warm radial glow, a
    secondary cool burst, some horizontal bands, and a few crisp geometric
    accents.  It compresses well visually and is designed to be recognisable
    when rendered in half-block mode.
    """
    w, h = 160, 100
    img = Image.new("RGB", (w, h), (10, 10, 30))
    draw = ImageDraw.Draw(img)

    # Warm radial glow near centre-right.
    cx, cy = int(w * 0.62), int(h * 0.45)
    for r in range(max(w, h), 0, -1):
        # Fade from warm orange to deep purple as we move out.
        t = r / max(w, h)
        red = int(255 * max(0.0, 1.0 - t * 1.3))
        green = int(180 * max(0.0, 1.0 - t * 1.5))
        blue = int(80 + 120 * t)
        colour = (red, green, blue)
        # Draw concentric circles — cheap approximation of a radial gradient.
        if r % 3 == 0:
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=colour)

    # Cool blue burst on the left.
    cx2, cy2 = int(w * 0.25), int(h * 0.7)
    for r in range(max(w, h) // 2, 0, -1):
        t = r / (max(w, h) // 2)
        colour = (
            int(40 + 60 * t),
            int(120 + 80 * (1 - t)),
            int(220 + 35 * (1 - t)),
        )
        if r % 3 == 0:
            draw.ellipse([cx2 - r, cy2 - r, cx2 + r, cy2 + r], fill=colour)

    # Horizontal bands for structure.
    band_colours = [
        (30, 20, 50),
        (60, 30, 70),
        (90, 50, 90),
        (50, 70, 110),
        (30, 90, 130),
        (20, 110, 140),
    ]
    band_height = h // len(band_colours)
    for i, col in enumerate(band_colours):
        y0 = i * band_height
        y1 = y0 + band_height
        draw.rectangle([0, y0, w, y1], fill=col)

    # Crisp white diagonal accent — helps the half-block render read clearly.
    draw.line([(10, h - 10), (w - 10, 10)], fill=(240, 240, 250), width=3)

    # A few small bright "stars" to add sparkle.
    import random
    random.seed(42)
    for _ in range(12):
        sx = random.randint(5, w - 5)
        sy = random.randint(5, h - 5)
        sr = random.randint(1, 3)
        draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 255, 230))

    return img


# Convenience: the demo image as bytes for `TermArt.from_bytes`.
def get_demo_image_bytes() -> bytes:
    """Return the demo image as PNG bytes."""
    return get_demo_image().convert("RGB").tobytes()  # caller should re-wrap if needed


def get_demo_image_png_bytes() -> bytes:
    """Return the demo image as a PNG-encoded byte string."""
    import io
    buf = io.BytesIO()
    get_demo_image().save(buf, format="PNG")
    return buf.getvalue()

# CLI for termart — the `termart` command.

# This module is intentionally thin: it parses args, resolves environment
# defaults, wires the demo image, and delegates rendering to core.py.  All
# visual logic lives in core.py / charset.py / color.py.
from __future__ import annotations

import os
import sys
from typing import Optional

import click

from . import __version__, core, demo, image, _env


# ---------------------------------------------------------------------------
# Environment helpers (imported here for CLI use)
# ---------------------------------------------------------------------------

def _default_width(force: Optional[int] = None) -> int:
    """Resolve output width: explicit override, terminal size, or fallback."""
    if force is not None:
        return force
    try:
        columns = os.get_terminal_size().columns
        if columns > 0:
            # Leave a small margin so the render never wraps.
            return max(40, columns - 2)
    except Exception:
        pass
    return 80


def _is_tty() -> bool:
    """True when stdout looks like an interactive terminal."""
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Demo wiring
# ---------------------------------------------------------------------------

def _render_demo(
    mode: str,
    width: Optional[int],
    height: Optional[int],
    color_enabled: bool,
    invert: bool,
    chars: Optional[str],
    font_ratio: float,
    scale_method: str,
    fit: str,
    output_path: Optional[str],
) -> None:
    """Render the built-in demo image using the resolved options."""
    img = demo.get_demo_image()

    # If no explicit width and we're on a TTY, use terminal width; else 100.
    if width is None:
        width = _default_width() if _is_tty() else 100

    ansi = core.render(
        img,
        mode=mode,
        width=width,
        height=height,
        color_enabled=color_enabled,
        invert=invert,
        chars=chars,
        font_ratio=font_ratio,
        scale_method=scale_method,
        fit=fit,
    )

    _emit_output(ansi, output_path=output_path, stdout=not bool(output_path))


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _emit_output(ansi: str, output_path: Optional[str], stdout: bool = True) -> None:
    """Write *ansi* to *output_path* and/or stdout."""
    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as fh:
                fh.write(ansi)
                if not ansi.endswith("\n"):
                    fh.write("\n")
        except OSError as exc:
            click.secho(f"termart: cannot write to {output_path!r}: {exc}", fg="red")
            sys.exit(1)

    if stdout:
        try:
            sys.stdout.write(ansi)
            if not ansi.endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.flush()
        except BrokenPipeError:
            # Pipe closed (e.g. `termart img | head`).  Exit quietly.
            sys.stderr.close()
            sys.exit(0)
        except Exception as exc:
            click.secho(f"termart: output error: {exc}", fg="red")
            sys.exit(1)


# ---------------------------------------------------------------------------
# Click command
# ---------------------------------------------------------------------------

@click.command(
    name="termart",
    context_settings=dict(help_option_names=["-h", "--help"]),
)
@click.version_option(version=__version__, prog_name="termart")
@click.option(
    "--demo", "-d",
    is_flag=True,
    help="Render the built-in demo image (zero setup, zero external files).",
)
@click.argument(
    "image",
    required=False,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
)
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["ascii", "halfblock", "shade"], case_sensitive=False),
    default="halfblock",
    show_default=True,
    help="Rendering mode: halfblock (default, highest fidelity), ascii (ranked-charset), shade (block ramps).",
)
@click.option(
    "--width",
    "-w",
    type=click.INT,
    default=None,
    help="Output width in character columns. Default: terminal width (TTY) or 80 (non-TTY).",
)
@click.option(
    "--height",
    "-H",
    type=click.INT,
    default=None,
    help="Output height in rows. If omitted, computed from aspect ratio and --font-ratio.",
)
@click.option(
    "--font-ratio",
    "-r",
    type=click.FLOAT,
    default=2.0,
    show_default=True,
    help="Aspect correction factor. Terminal chars are typically ~2x taller than wide; raise this for thinner output, lower for taller.",
)
@click.option(
    "--scale",
    type=click.Choice(["nearest", "bicubic", "lanczos"], case_sensitive=False),
    default="lanczos",
    show_default=True,
    help="Resize filter: lanczos (default, best quality), bicubic, nearest (fastest).",
)
@click.option(
    "--fit",
    type=click.Choice(["shrink", "stretch", "contain", "cover"], case_sensitive=False),
    default="contain",
    show_default=True,
    help="How to handle aspect-ratio mismatch: contain (fit within width/height, preserve ratio, pad if needed), cover (fill, crop overflow), stretch (ignore aspect), shrink (contain but never upscale beyond source).",
)
@click.option(
    "--chars",
    "-c",
    type=str,
    default=None,
    help="Character ramp for ASCII mode. Either a built-in name (classic, detailed, shade, classic-spaced, dark-only) or a custom string (e.g. '@%#*+=-:. ').",
)
@click.option(
    "--no-color",
    is_flag=True,
    help="Monochrome output. No ANSI colour codes in any mode.",
)
@click.option(
    "--invert",
    is_flag=True,
    help="Swap foreground/background colours. Useful on light-background terminals; primarily affects half-block mode (top/bottom pixel assignment).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False),
    default=None,
    help="Write ANSI output to this file instead of (or in addition to) stdout.",
)
@click.option(
    "--stdout",
    is_flag=True,
    help="Explicitly write to stdout (useful for scripts that need to ensure stdout output).",
)
def main(
    demo_flag: bool,
    image: Optional[str],
    mode: str,
    width: Optional[int],
    height: Optional[int],
    font_ratio: float,
    scale_method: str,
    fit: str,
    chars: Optional[str],
    no_color: bool,
    invert: bool,
    output_path: Optional[str],
    stdout_flag: bool,
) -> None:
    """Render any image as beautiful ANSI half-block art in your terminal.

    ONE COMMAND, ZERO SETUP.  Try it right now:

        termart --demo

    No image to download.  The built-in demo renders immediately.

    For your own image:

        termart photo.jpg

    For more, see the README or `termart --help`.
    """
    # --version and --help are handled by Click automatically.
    color_enabled = not no_color

    # --demo takes precedence over a positional image.
    if demo_flag:
        _render_demo(
            mode=mode,
            width=width,
            height=height,
            color_enabled=color_enabled,
            invert=invert,
            chars=chars,
            font_ratio=font_ratio,
            scale_method=scale_method,
            fit=fit,
            output_path=output_path,
        )
        return

    if image is None:
        # No image, no --demo: print help and exit with a hint.
        click.echo(main.get_help(click.Context(main)))
        click.echo("")
        click.secho("Nothing to render. Pass an image path or use --demo.", fg="yellow")
        sys.exit(0)

    # Resolve width from environment when not explicit.
    if width is None:
        width = _default_width() if _is_tty() else 100

    try:
        img = image.load_image(image)
    except FileNotFoundError:
        click.secho(f"termart: image not found: {image}", fg="red")
        sys.exit(1)
    except ValueError as exc:
        click.secho(f"termart: cannot read image {image!r}: {exc}", fg="red")
        sys.exit(1)

    # Warn when the image is smaller than the requested width and we'll be
    # returning it at native size (no upscale in v1).
    src_w, src_h = img.size
    if width > src_w:
        click.secho(
            f"termart: image width ({src_w}px) is less than requested width "
            f"({width} cols). Outputting at native size — no upscale in v1.",
            fg="yellow",
        )

    ansi = core.render(
        img,
        mode=mode,
        width=width,
        height=height,
        color_enabled=color_enabled,
        invert=invert,
        chars=chars,
        font_ratio=font_ratio,
        scale_method=scale_method,
        fit=fit,
    )

    _emit_output(ansi, output_path=output_path, stdout=not bool(output_path) or stdout_flag)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()

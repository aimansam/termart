# termart

**Turn any image into beautiful terminal art — half-block characters, color, and multiple charsets.**

Render images in your terminal using half-block characters (▄▀) for double the vertical resolution, with color support where possible, multiple output modes, and a built-in demo.

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Click](https://img.shields.io/badge/cli-click-lightgrey.svg)](https://click.palletsprojects.com/)

## Quickstart

```bash
pip install -e .
```

```bash
# Convert an image to terminal art
termart image.jpg

# Half-block mode (higher resolution)
termart image.jpg --mode halfblock

# With color
termart image.jpg --color

# Resize to fit terminal
termart image.jpg --width 120

# Run the built-in demo
termart demo
```

## What it does

termart renders images directly in your terminal using Unicode block characters. Instead of simple ASCII (which gives you one character per pixel block), termart uses half-block characters (▄ and ▀) to render two rows of pixels per character — doubling the vertical resolution and producing noticeably sharper output.

### Output modes

- **ASCII** — classic `./-Oo`로 #-+=~ characters, good for quick previews
- **Half-block** — ▄▀ characters, 2x vertical resolution, the default and recommended mode
- **Shade** — uses `░▒▓█` gradient characters for smooth grayscale
- **Color** — ANSI color codes when supported, per-character or per-block coloring

### Key features

- **Half-block rendering** — double vertical resolution vs plain ASCII
- **Color support** — extracts dominant colors and renders with ANSI codes when terminal supports it
- **Multiple charsets** — choose from ranked, block, shade, or provide your own character set
- **Resize and scale** — width/height controls, fit-to-terminal, scale methods (nearest, bilinear)
- **Demo mode** — built-in sample image, try `termart demo` without any image file
- **Output to file** — save rendered art to a text file with `--output`
- ** inverts** — `--invert` for dark-on-light terminals
- **Font ratio adjustment** — compensate for non-square terminal fonts

## Installation

```bash
git clone https://github.com/yourusername/termart.git
cd termart
pip install -e .
```

Requires Python 3.9+ and Click:

```bash
pip install click
```

## Usage

### Basic conversion

```bash
termart photo.jpg
```

Renders `photo.jpg` to terminal using half-block mode with grayscale shading.

### Half-block with color

```bash
termart photo.jpg --mode halfblock --color
```

### Resize to specific width

```bash
termart photo.jpg --width 120 --height 40
```

### Use a specific charset

```bash
termart photo.jpg --chars " .:-=+*#%@"
```

### Save to file

```bash
termart photo.jpg --output art.txt
# Open art.txt in any text editor or cat it in terminal
```

### Run demo

```bash
termart demo
# Renders the built-in sample image with current settings
termart demo --mode ascii --color
# Try different modes with the demo
```

### Invert for light backgrounds

```bash
termart photo.jpg --invert
```

### Programmatic use

```python
from termart import render, render_halfblock, TermArt

# Quick render to string
art = render("photo.jpg", mode="halfblock", width=120)
print(art)

# With more control
ta = TermArt(
    image_path="photo.jpg",
    mode="halfblock",
    width=120,
    color_enabled=True,
    charset="builtin_ranked",
)
art = ta.render()
print(art)

# Render to file
with open("output.txt", "w") as f:
    f.write(art)
```

## Project structure

```
termart/
├── __init__.py    # Public API: render, render_halfblock, render_ascii, render_shade, TermArt
├── __main__.py    # python -m termart entry point
├── cli.py         # Click CLI interface — all command-line options
├── core.py        # Core rendering engine — image processing, character mapping, output generation
├── charset.py     # Character set definitions and ranking
├── color.py       # Color extraction, ANSI color code generation
├── image.py       # Image loading, resizing, pixel access helpers
├── demo.py        # Built-in demo image generator
└── _env.py       # Environment detection (terminal size, color support)
```

## Requirements

- Python 3.9+
- Pillow 10.0+ (image loading and processing)
- Click 8.0+ (CLI framework)

```bash
pip install Pillow click
```

## License

MIT License — see [LICENSE](LICENSE).

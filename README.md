# NASA Media Downloader - Professional Edition

A professional, cross-platform tool for downloading images and videos from NASA's media library. Features a modular architecture, desktop CLI, and Android APK support.

![Version](https://img.shields.io/badge/version-2.1.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.9+-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)

---

## Features

### Media Downloads
- **Images**: Download high-resolution space imagery in multiple quality levels
- **Videos**: Download space videos with intelligent quality detection
- **Metadata**: Save complete metadata as JSON and human-readable TXT files
- **Quality Options**: Small, Medium, Large, Original, or All qualities simultaneously

### Visual Experience
- **Procedural Galaxy Animation**: Mathematically-generated 5-arm spiral galaxy
- **Nebula Overlay**: Multi-octave noise-based cosmic clouds
- **Flying UFO**: Animated spacecraft with motion effects
- **Enhanced Starfield**: Twinkling stars with shooting star effects

### Technical Features
- **Adaptive Throttling**: Automatically adjusts download speed to avoid rate limits
- **Concurrent Downloads**: Multi-threaded downloads (1-12 workers)
- **Smart Retry Logic**: Automatic retry with exponential backoff
- **Progress Tracking**: Real-time progress bars
- **Security**: Input sanitization, path traversal prevention, HTTPS-only
- **Cross-Platform**: Desktop CLI and Android APK support

---

## Project Structure

```
nasa-media-downloader/
├── src/nasa_downloader/          # Main package
│   ├── __init__.py
│   ├── __main__.py               # Entry point
│   ├── core/                     # Configuration, models, exceptions
│   │   ├── config.py
│   │   ├── models.py
│   │   └── exceptions.py
│   ├── api/                      # NASA API client
│   │   ├── client.py
│   │   ├── session.py
│   │   └── quality.py            # Intelligent quality detection
│   ├── downloader/               # Download engine
│   │   ├── engine.py
│   │   ├── throttle.py
│   │   ├── tasks.py
│   │   └── metadata.py           # Fixed metadata saving
│   ├── cli/                      # Command-line interface
│   │   ├── app.py                # Click-based CLI
│   │   └── prompts.py
│   └── ui/                       # Terminal UI
│       ├── terminal.py
│       ├── starfield.py
│       ├── intro.py
│       └── themes.py
├── android/                      # Android/Kivy app
│   ├── main.py
│   ├── buildozer.spec
│   └── nasa_downloader.kv
├── tests/                        # Test suite
├── .github/workflows/            # CI/CD
│   └── build-apk.yml
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

---

## Installation

### Desktop CLI

```bash
# Clone the repository
git clone https://github.com/your-username/nasa-media-downloader.git
cd nasa-media-downloader

# Install dependencies
pip install -r requirements.txt

# Or install as package
pip install -e .
```

### Android APK

The APK is automatically built via GitHub Actions. Download from the Actions tab or build locally:

```bash
cd android
pip install buildozer
buildozer android debug
```

---

## Usage

### Interactive Mode (Recommended)

```bash
python -m nasa_downloader interactive
```

Or simply:

```bash
python -m nasa_downloader
```

This launches the full experience with animations and interactive prompts.

### Command Line Mode

For automation and scripts:

```bash
# Download Mars images
python -m nasa_downloader download --query "mars" --limit 50 --quality orig

# Download ISS videos with metadata
python -m nasa_downloader download --query "ISS" --videos --metadata --quality large

# Download all qualities
python -m nasa_downloader download --query "nebula" --images --videos --quality all --limit 100
```

### CLI Reference

```bash
python -m nasa_downloader download [OPTIONS]

Options:
  -q, --query TEXT       Search query (required)
  -o, --output PATH      Output directory
  -Q, --quality TEXT     Quality: 1=small, 2=medium, 3=large, 4=orig, 5=all
  -n, --limit INT        Maximum items to download
  --rate FLOAT           Delay between requests (default: 1.0)
  --workers INT          Concurrent download threads (default: 6)
  --min-workers INT      Minimum workers for adaptive mode (default: 1)
  --max-workers INT      Maximum workers for adaptive mode (default: 12)
  --no-adaptive          Disable adaptive throttling
  --images/--no-images   Download images (default: yes)
  --videos/--no-videos   Download videos (default: no)
  --metadata/--no-metadata  Save metadata files (default: yes)
```

### Interactive Mode Options

```bash
python -m nasa_downloader interactive [OPTIONS]

Options:
  --skip-intro    Skip the intro animation
  --rate FLOAT    Delay between requests
  --workers INT   Concurrent download threads
```

---

## Output Structure

```
NASA-Downloads/
└── your_search_query/
    ├── mission_manifest.json
    ├── logs/
    │   └── nasa_downloader.log
    ├── Images/
    │   ├── Low/
    │   │   ├── Files/
    │   │   └── Metadata/
    │   ├── Medium/
    │   ├── High/
    │   └── Original/
    └── Videos/
        ├── Low/
        ├── Medium/
        ├── High/
        └── Original/
```

---

## Quality Levels

| Quality    | CLI Option       | Description                    |
|------------|------------------|--------------------------------|
| **Small**  | `1` or `small`   | Low resolution, fast downloads |
| **Medium** | `2` or `medium`  | Balanced quality and size      |
| **Large**  | `3` or `large`   | High resolution                |
| **Original** | `4` or `orig`  | Best quality, largest files    |
| **All**    | `5` or `all`     | All 4 quality levels           |

---

## Development

### Setup Development Environment

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Format code
black src/
ruff check src/

# Type checking
mypy src/
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=nasa_downloader --cov-report=html

# Run specific test file
pytest tests/test_quality.py
```

---

## Bug Fixes in v2.1.0

### Bug #1: Metadata Saving
**Problem**: Metadata was only saved to the first quality directory
**Fix**: Now saves metadata to ALL selected quality directories

### Bug #2: Video Quality Detection
**Problem**: Simple string matching failed on many video URLs
**Fix**: Implemented intelligent scoring system based on:
- Resolution patterns (1080p, 720p, 480p)
- Quality keywords (orig, master, preview)
- Fallback to best available

---

## API Information

This tool uses the **NASA Images and Video Library API**:
- **Endpoint**: `https://images-api.nasa.gov`
- **No API Key Required**: Completely free and public
- **Content**: 140,000+ images and videos

---

## Troubleshooting

### Downloads are slow
- Reduce workers: `--workers 3`
- Increase rate limit: `--rate 2.0`

### Rate limited (429 errors)
- The adaptive throttling handles this automatically
- Or use: `--workers 2 --max-workers 4 --rate 2.0`

### Animation doesn't display
- Use a modern terminal (Windows Terminal, iTerm2)
- Or use `--skip-intro` flag

---

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Run tests: `pytest`
4. Submit a pull request

---

## License

MIT License - Feel free to use, modify, and distribute.

---

## Credits

- **NASA Images API**: For free access to incredible space media
- **Python Community**: For amazing libraries
- **Contributors**: Everyone who helps improve this tool

---

*Happy downloading, space explorer!*

```
    ╭───╮
   ╱ ◉ ◉ ╲
  ╱───────╲
 ▔▔▔▔▔▔▔▔▔▔
```

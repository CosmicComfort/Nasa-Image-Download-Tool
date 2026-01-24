# 🚀 NASA Media Downloader - Enhanced Space Edition

A powerful, cross-platform tool to search and download images and videos from NASA's official media library with spectacular procedurally-generated space visuals.

![Version](https://img.shields.io/badge/version-2.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)

---

## ✨ Features

### 🎬 **Media Downloads**
- **Images**: Download high-resolution space imagery in multiple quality levels
- **Videos**: Download space videos with quality selection
- **Metadata**: Save complete metadata as JSON and human-readable TXT files
- **Quality Options**: Small, Medium, Large, Original, or All qualities simultaneously

### 🌌 **Spectacular Visuals**
- **Procedural Galaxy Animation**: Mathematically-generated 5-arm spiral galaxy with 1400+ particles
- **Nebula Overlay**: Multi-octave noise-based cosmic clouds
- **Flying UFO**: Animated spacecraft with bobbing motion and alternating lights
- **Enhanced Starfield**: Persistent twinkling stars with shooting star effects
- **Command Deck Interface**: Cyberpunk-inspired terminal UI with color-coded status messages

### 🔧 **Technical Features**
- **Adaptive Throttling**: Automatically adjusts download speed to avoid API rate limits
- **Concurrent Downloads**: Multi-threaded downloads with configurable worker count (1-12)
- **Smart Retry Logic**: Automatic retry with exponential backoff for failed downloads
- **Progress Tracking**: Real-time progress bars with tqdm integration
- **Safe File Handling**: Automatic fallback to writable directories
- **Organized Output**: Separate folders for Images/Videos and quality levels
- **Comprehensive Logging**: Rotating log files with detailed operation history

### 📁 **Folder Structure**
```
NASA-Downloads/
└── your_search_query/
    ├── mission_manifest.json
    ├── logs/
    │   └── nasa_downloader.log
    ├── Images/
    │   ├── Low/
    │   │   ├── Files/
    │   │   │   ├── 0001_image_title.jpg
    │   │   │   └── 0002_another_image.jpg
    │   │   └── Metadata/
    │   │       ├── 0001_image_title.json
    │   │       └── 0001_image_title.txt
    │   ├── Medium/
    │   ├── High/
    │   └── Original/
    └── Videos/
        ├── Low/
        │   ├── Files/
        │   │   └── 0001_video_title.mp4
        │   └── Metadata/
        ├── Medium/
        ├── High/
        └── Original/
```

---

## 🚀 Quick Start

### Installation

1. **Install Python** (3.8 or higher required)
   - Download from [python.org](https://www.python.org/)
   - Ensure "Add Python to PATH" is checked during installation

2. **Install Dependencies**
   ```bash
   # Navigate to the tool directory
   cd NASA-DownloadTool
   
   # Install required packages
   pip install -r requirements.txt
   ```

### Requirements File
Create a `requirements.txt` file with:
```
requests>=2.28.0
urllib3>=1.26.0
tqdm>=4.65.0
```

---

## 💻 Usage

### Interactive Mode (Recommended for First-Time Users)

Simply run the script and follow the beautiful command-deck prompts:

```bash
python nasa_downloader_v2.py
```

**What happens:**
1. 🌌 **Galaxy Zoom Animation**: Watch a procedurally-generated galaxy with a flying UFO
2. 📝 **Query Input**: Enter your search terms (e.g., "mars rover", "nebula", "ISS")
3. 📂 **Output Location**: Choose where to save files (default: `./NASA-Downloads`)
4. 🎨 **Quality Selection**: Pick image/video quality via interactive menu
5. 🎬 **Media Type**: Choose Images, Videos, or Both
6. 📊 **Metadata**: Decide whether to download metadata files
7. 🔢 **Download Limit**: Set maximum items or download everything
8. 🚀 **Launch**: Confirm and begin the mission!

---

### Command Line Mode (For Automation)

For scripts, automation, or when you know exactly what you want:

#### Basic Examples

**Download 50 Mars images (original quality):**
```bash
python nasa_downloader_v2.py --query "mars" --output ./mars_images --qualities 4 --limit 50 --images --no-prompt
```

**Download all available ISS videos (all qualities):**
```bash
python nasa_downloader_v2.py --query "international space station" --qualities 5 --videos --metadata --no-prompt
```

**Download both images and videos with metadata:**
```bash
python nasa_downloader_v2.py --query "apollo 11" --images --videos --metadata --qualities orig --limit 100 --no-prompt
```

#### Full CLI Reference

```bash
python nasa_downloader_v2.py [OPTIONS]

Required for --no-prompt:
  --query, -q TEXT          Search query (required in non-interactive mode)

Optional:
  --output, -o PATH         Output directory (default: ./NASA-Downloads)
  --qualities, -Q TEXT      Quality selection:
                            1 = small, 2 = medium, 3 = large, 4 = orig, 5 = all
                            Or use names: small,medium,large,orig
  --limit, -n INT          Maximum items to download (default: unlimited)
  --rate FLOAT             Delay between requests in seconds (default: 1.0)
  --workers INT            Number of concurrent download threads (default: 6)
  --min-workers INT        Minimum workers for adaptive mode (default: 1)
  --max-workers INT        Maximum workers for adaptive mode (default: 12)
  --no-adaptive            Disable adaptive throttling
  --images                 Download images
  --videos                 Download videos
  --metadata               Download metadata (JSON + TXT)
  --no-prompt              Non-interactive mode (requires --query)
```

---

## 🎨 Quality Levels Explained

| Quality    | CLI Option | Description                          | Typical Size (Image) |
|------------|------------|--------------------------------------|----------------------|
| **Small**  | `1` or `small` | Low resolution, fast downloads   | ~50-200 KB          |
| **Medium** | `2` or `medium` | Balanced quality and size       | ~200-500 KB         |
| **Large**  | `3` or `large` | High resolution                  | ~500 KB - 2 MB      |
| **Original** | `4` or `orig` | Best quality, largest files    | ~1-5 MB             |
| **All**    | `5` or `all` | Downloads all 4 quality levels   | ~2-8 MB total       |

**For Videos:** Quality levels vary based on available formats. The tool automatically selects the best available quality for each level.

---

## 📋 Usage Examples

### Example 1: Space Exploration Collection
```bash
python nasa_downloader_v2.py \
  --query "space exploration" \
  --output ./space_collection \
  --qualities all \
  --images \
  --videos \
  --metadata \
  --limit 200 \
  --no-prompt
```

### Example 2: Quick Mars Image Grab
```bash
python nasa_downloader_v2.py \
  -q "mars curiosity rover" \
  -o ./mars \
  -Q orig \
  --images \
  --limit 25 \
  --no-prompt
```

### Example 3: Educational Video Archive
```bash
python nasa_downloader_v2.py \
  --query "earth from space" \
  --videos \
  --qualities medium,large \
  --metadata \
  --workers 4 \
  --no-prompt
```

### Example 4: Hubble Telescope Images
```bash
python nasa_downloader_v2.py \
  --query "hubble telescope" \
  --images \
  --qualities orig \
  --metadata \
  --limit 100 \
  --rate 0.5 \
  --no-prompt
```

---

## 🔧 Advanced Configuration

### Adaptive Throttling

The tool includes **intelligent adaptive throttling** that automatically adjusts download speed based on API responses:

- **Success Rate > 95%**: Increases worker threads (up to `--max-workers`)
- **Throttle Rate > 8%**: Reduces workers by 50% and adds cooldown period
- **Failure Rate > 25%**: Reduces workers by 30% and adds cooldown

**Disable adaptive mode** for consistent behavior:
```bash
python nasa_downloader_v2.py --query "mars" --no-adaptive --workers 3
```

### Performance Tuning

**Faster downloads** (use with caution - may trigger rate limits):
```bash
--workers 10 --rate 0.5 --max-workers 12
```

**Conservative/Safe** (recommended for large downloads):
```bash
--workers 3 --rate 1.5 --min-workers 2 --max-workers 6
```

### Logging

Logs are automatically saved to `<output_directory>/<query>/logs/nasa_downloader.log`

- **Rotating logs**: Max 3MB per file, keeps 3 backup files
- **Console output**: Real-time status updates
- **Log levels**: INFO, WARNING, ERROR

---

## 🌟 Visual Features

### Intro Animation Sequence
1. **Deep Space View** (frames 0-6): Distant galaxy view with wide perspective
2. **Approach** (frames 7-38): Smooth zoom toward galaxy center with camera wobble
3. **UFO Appearance** (frame 15+): Flying saucer enters scene with bobbing animation
4. **Close-Up** (frames 39-50): Detailed view of galaxy core and arms
5. **Duration**: ~4.5 seconds, 50 frames

### Starfield Effects
- **Twinkling Stars**: 7 different star characters with brightness variation
- **Shooting Stars**: Random meteor streaks across the top of terminal
- **Persistent Display**: Runs in background during entire session
- **Adaptive**: Automatically adjusts to terminal resize

### Color Scheme
- 🔵 **Cyan**: Borders, headers, system messages
- 💛 **Yellow**: User input prompts, warnings
- 💚 **Green**: Success messages, confirmations
- 🔴 **Red**: Errors, critical messages
- 💜 **Magenta**: Video-related operations
- **Bold**: Important titles and emphasis

---

## 🛡️ Safety Features

- ✅ **Automatic Fallback**: If specified directory isn't writable, falls back to:
  1. User's home directory (`~/NASA-Downloads`)
  2. System temp directory (`/tmp/NASA-Downloads_temp`)
  3. Generated temp directory as last resort

- ✅ **Skip Existing Files**: Won't re-download files that already exist
- ✅ **Graceful Interruption**: Ctrl+C cleanly stops downloads and saves progress
- ✅ **Error Recovery**: Automatic retry with exponential backoff
- ✅ **Mission Manifest**: Every search saves a manifest file with all parameters

---

## 📊 NASA API Information

This tool uses the **NASA Images and Video Library API**:
- **Endpoint**: `https://images-api.nasa.gov`
- **No API Key Required**: Completely free and public
- **Rate Limits**: Unofficial, but tool uses adaptive throttling to be respectful
- **Content**: 140,000+ images and videos from NASA's archives

**Search Tips:**
- Use specific terms: `"apollo 11 moon landing"` vs just `"moon"`
- Try mission names: `"curiosity rover"`, `"voyager"`, `"hubble"`
- Use NASA centers: `"kennedy space center"`, `"JPL"`
- Combine terms: `"mars surface color"`

---

## ❓ FAQ

**Q: Do I need a NASA API key?**  
A: No! The NASA Images API is completely public and free.

**Q: How long does it take to download 100 images?**  
A: With default settings (~6 workers, 1s rate limit), approximately 5-10 minutes depending on file sizes.

**Q: Can I run multiple instances simultaneously?**  
A: Yes, but use lower worker counts (2-3) per instance to avoid overwhelming the API.

**Q: What if the animation doesn't display correctly?**  
A: Use a modern terminal (Windows Terminal, iTerm2, or most Linux terminals). The tool will still work fine even if visuals are garbled.

**Q: Where are the logs stored?**  
A: In `<output_directory>/<search_query>/logs/nasa_downloader.log`

**Q: Can I resume interrupted downloads?**  
A: Yes! Run the same command again - the tool skips files that already exist.

**Q: Why are some quality levels missing?**  
A: Not all media has all quality levels. The tool downloads whatever is available.

---

## 🐛 Troubleshooting

### Issue: "No items found"
- Check your search query spelling
- Try broader terms (e.g., "mars" instead of "mars curiosity rover sol 234")
- Verify internet connection

### Issue: Downloads are very slow
- Reduce `--workers` count (try 3-4)
- Increase `--rate` delay (try 1.5-2.0)
- Check your internet connection speed

### Issue: "Permission denied" when saving files
- Don't worry! Tool automatically falls back to safe directories
- Or specify a directory you own: `--output ~/Documents/NASA`

### Issue: Animation doesn't show
- Your terminal may not support ANSI codes
- Try Windows Terminal, iTerm2, or similar modern terminal
- Use `--no-prompt` to skip animations

### Issue: Rate limited / Too many 429 errors
- The adaptive throttling should handle this automatically
- If not, reduce workers: `--workers 2 --max-workers 4`
- Increase rate limit: `--rate 2.0`

---

## 🤝 Contributing

Found a bug? Have a feature request? Contributions welcome!

---

## 📜 License

MIT License - Feel free to use, modify, and distribute.

---

## 🙏 Credits

- **NASA Images API**: For providing free access to incredible space media
- **Python Community**: For the amazing libraries (requests, tqdm, urllib3)
- **Space Enthusiasts**: For exploring the cosmos with us

---

## 🌠 Enjoy Your Journey Through the Cosmos!

```
    ╭───╮    
   ╱ ◉ ◉ ╲   
  ╱───────╲  
 ▔▔▔▔▔▔▔▔▔▔ 
```

*Happy downloading, space explorer!* 🚀✨

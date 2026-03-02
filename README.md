# let-me-send-pls

Fixes "file too large" so you can just send it. A desktop app that splits videos to fit Discord, Slack, WhatsApp, and other chat upload limits.

## Features

- **Platform-aware splitting** — select Discord, Slack, or WhatsApp and the correct size limit is applied automatically
- **Drag & drop** — drop a video file onto the window or click to browse
- **Visual previews** — square thumbnail previews of each resulting part
- **Reveal in file browser** — click the folder icon on any part to open it in Finder / Files / Explorer
- **Cross-platform** — runs on macOS, Linux, and Windows
- **Extensible** — designed so new platforms and file types can be added easily

## Platform size limits

| Platform  | Tier         | Max size per part |
|-----------|--------------|-------------------|
| Discord   | Free         | 10 MB             |
| Discord   | Nitro Basic  | 50 MB             |
| Discord   | Nitro        | 500 MB            |
| Slack     | All plans    | 1 GB              |
| WhatsApp  | Standard     | 180 MB            |

## Prerequisites

| Dependency             | Install                                                                                              |
|------------------------|------------------------------------------------------------------------------------------------------|
| **Python 3.10+**       | [python.org](https://www.python.org/downloads/)                                                      |
| **ffmpeg** (+ ffprobe) | macOS: `brew install ffmpeg` · Linux: `sudo apt install ffmpeg` · Windows: `winget install ffmpeg`    |

## Quick start

```bash
# 1. Clone the repo
git clone <repo-url> && cd let-me-send-pls

# 2. Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python main.py
```

## Building a standalone executable

You can package the app into a single executable with [PyInstaller](https://pyinstaller.org):

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "LetMeSendPls" main.py
```

The binary will be in `dist/LetMeSendPls`.

## Architecture

```
main.py              # Entry point
app/
  platforms.py       # Platform & tier definitions  (add new platforms here)
  splitter.py        # Base Splitter ABC + VideoSplitter  (add file types here)
  worker.py          # Background QThread for splitting
  main_window.py     # Main application window
  widgets.py         # UI components: DropZone, PlatformPicker, ResultCard, ResultsPanel
  theme.py           # Dark theme styling  (Catppuccin Mocha palette)
```

### Adding a new platform

Edit `PLATFORM_TIERS` in `app/platforms.py`:

```python
PlatformTier("Telegram", "Default", 2000),
```

### Adding a new file type

1. Create a new `Splitter` subclass in `app/splitter.py` (see `VideoSplitter` for reference).
2. Register it in the `_SPLITTERS` list at the bottom of the file.

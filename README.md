# YT Downloader

A cross-platform desktop GUI for downloading YouTube videos and playlists, powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [ffmpeg](https://ffmpeg.org/).

![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey)

---

## Features

- Download single videos or full playlists
- Quality selection: Best, 720p, 1080p, 1440p, 2160p (4K), 4320p (8K), Audio Only
- Cookie support — load from a `.txt` file or extract live from Chrome, Brave, Firefox, or Edge
- Playlist range filter (e.g. `1-50`)
- Real-time progress bar and streaming log output
- Stop button to cancel in-progress downloads
- **Automatic first-run setup** — installs `yt-dlp`, `ffmpeg`, and `yt-dlp-ejs` via pip on first launch when running from source (one-time only); the standalone app has everything bundled
- **Check for Updates** button — upgrades `yt-dlp` and `ffmpeg` to the latest versions at any time
- Works as a plain Python script **or** as a standalone PyInstaller-packaged `.app` / `.exe`

---

## Requirements

- Python 3.8 or newer
- `tkinter` (bundled with most Python installers; on Linux: `sudo apt install python3-tk`)
- **Node.js v20+** — required to solve YouTube's signature/n-challenge (install from [nodejs.org](https://nodejs.org) or via your package manager). The [`yt-dlp-ejs`](https://github.com/yt-dlp/yt-dlp-ejs) solver script is installed automatically via pip.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/craftedbypratik/YT-Downloader-PS.git
cd YT-Downloader-PS

# 2. (Optional) create a virtual environment
python3 -m venv .venv && source .venv/bin/activate   # macOS / Linux
# python -m venv .venv && .venv\Scripts\activate      # Windows

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Run
python3 yt_gui.py
```

On the **very first launch** when running from source (dependencies not yet installed), a setup dialog will appear and install everything automatically. This only happens once. When running the standalone `.app` / `.exe`, all dependencies are already bundled — no setup step needed.

> **Tip:** You can also run `python3 install_requirements.py` to install everything from the command line before the first GUI launch.

---

## Building a Standalone App (PyInstaller)

### Prerequisites

1. Install PyInstaller and all Python dependencies (including `imageio-ffmpeg`, which ships its own pre-built ffmpeg binary — no manual ffmpeg download needed):

   ```bash
   pip install pyinstaller
   pip install -r requirements.txt
   ```

### Build

```bash
pyinstaller yt_gui.spec
```

The spec automatically collects the ffmpeg binary from `imageio-ffmpeg` — **no files need to be placed anywhere manually**.

The output is placed in `dist/`:

- **macOS** → `dist/YTDownloader.app`
- **Windows** → `dist/YTDownloader.exe`
- **Linux** → `dist/YTDownloader`

> **Note:** Build on the target platform. Cross-compilation is not supported by PyInstaller.

---

## Project Structure

```
yt-downloader/
├── yt_gui.py               # Main application (entry point)
├── install_requirements.py # CLI dependency installer / helper script
├── yt_gui.spec             # PyInstaller build spec (cross-platform)
├── requirements.txt        # Python dependencies
├── icon.icns               # App icon (macOS)
└── icon.ico                # App icon (Windows)
```

---

## How It Works

| Scenario | yt-dlp resolution | ffmpeg resolution |
|----------|-------------------|-------------------|
| Script (`python yt_gui.py`) | system `PATH` → `python -m yt_dlp` (pip-installed) | `imageio-ffmpeg` pip binary → system `PATH` |
| Frozen app (PyInstaller) | bundled inside the app via self-invocation proxy (`__ytdlp__`) | `imageio-ffmpeg` binary bundled by PyInstaller at build time |

**Everything is automatic — no binaries are committed to this repository:**

- **Script mode** — first launch installs `yt-dlp`, `imageio-ffmpeg`, and `yt-dlp-ejs` via pip (one-time only).
- **Frozen app** — `yt-dlp`, `yt-dlp-ejs`, and `ffmpeg` are all bundled inside the packaged app; no internet access or setup required on first launch.
- **Check for Updates** button — re-runs the above in a background dialog at any time.

---

## Security Notes

- All subprocess calls use argument lists (never `shell=True`), preventing shell-injection attacks.
- The URL and file paths entered by the user are passed directly as arguments to `yt-dlp` and are never evaluated or interpolated into a shell string.
- The `pip install --upgrade` calls during setup/update run under the current user's permissions only.

---

## License

MIT © Pratik

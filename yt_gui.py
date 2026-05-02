import sys
import os

# ─── PyInstaller frozen-mode yt-dlp proxy ────────────────────────────────────
# When the frozen app is invoked with '__ytdlp__' as the first argument it
# delegates entirely to yt-dlp's main(), using the bundled Python environment
# (which includes yt-dlp-ejs).  This is how the GUI subprocess-calls yt-dlp
# in frozen mode so all optional libraries are available.
if getattr(sys, "frozen", False) and len(sys.argv) > 1 and sys.argv[1] == "__ytdlp__":
    del sys.argv[1]          # remove the sentinel; rest of argv goes to yt-dlp
    from yt_dlp import main as _ytdlp_main
    _ytdlp_main()
    sys.exit(0)
# ─────────────────────────────────────────────────────────────────────────────

import tkinter as tk
from tkinter import ttk, filedialog
import subprocess
import threading
import queue
import platform
import shutil

# ─── App Data Directory ───────────────────────────────────────────────────────
APP_DATA_DIR   = os.path.join(os.path.expanduser("~"), ".yt-downloader")
APP_BIN_DIR    = os.path.join(APP_DATA_DIR, "bin")
FIRST_RUN_FLAG = os.path.join(APP_DATA_DIR, ".setup_done")
os.makedirs(APP_DATA_DIR, exist_ok=True)

# yt-dlp GitHub latest-release download URLs (one binary per platform)
_YTDLP_URLS = {
    "Darwin":  "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos",
    "Windows": "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
    "Linux":   "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp",
}
_YTDLP_BIN = {
    "Darwin":  "yt-dlp",
    "Windows": "yt-dlp.exe",
    "Linux":   "yt-dlp",
}

# ─── Dependency Management ────────────────────────────────────────────────────

def get_ytdlp_cmd():
    """
    Return yt-dlp invocation as a list.

    Frozen app  → re-invoke self with '__ytdlp__' sentinel so the bundled
                  Python (with yt-dlp-ejs) handles the download.
    Script mode → system PATH → python -m yt_dlp fallback.
    Returns [] if nothing is found.
    """
    if getattr(sys, "frozen", False):
        # Use the frozen app's own bundled Python + yt-dlp + yt-dlp-ejs
        return [sys.executable, "__ytdlp__"]

    # Script mode
    p = shutil.which("yt-dlp")
    if p:
        return [p]
    try:
        subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return [sys.executable, "-m", "yt_dlp"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return []


def get_ffmpeg_path():
    """
    Return path to an ffmpeg binary.
    - In frozen mode: imageio_ffmpeg data files were bundled by PyInstaller,
      so get_ffmpeg_exe() resolves to the binary inside the .app/_MEIPASS.
    - In script mode: imageio_ffmpeg was pip-installed, same API works.
    Falls back to the system PATH if imageio_ffmpeg is unavailable.
    """
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        pass
    return shutil.which("ffmpeg")


def download_ytdlp_binary(log_cb=None):
    """
    Download the latest yt-dlp binary from GitHub releases into APP_BIN_DIR.
    Used by the frozen app at first-run and when 'Check for Updates' is clicked.
    Returns True on success, False on failure.
    """
    import urllib.request
    system = platform.system()
    url    = _YTDLP_URLS.get(system)
    if not url:
        if log_cb:
            log_cb(f"  ✗ Automatic yt-dlp download is not supported on {system}.")
        return False

    os.makedirs(APP_BIN_DIR, exist_ok=True)
    dest = os.path.join(APP_BIN_DIR, _YTDLP_BIN.get(system, "yt-dlp"))
    if log_cb:
        log_cb("→ yt-dlp: downloading latest release from GitHub…")
    try:
        urllib.request.urlretrieve(url, dest)
        if system != "Windows":
            os.chmod(dest, 0o755)
        if log_cb:
            log_cb("  ✓ yt-dlp downloaded successfully\n")
        return True
    except Exception as exc:
        if log_cb:
            log_cb(f"  ✗ Download failed: {exc}\n")
        return False


def is_setup_done():
    return os.path.isfile(FIRST_RUN_FLAG)


def mark_setup_done():
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    open(FIRST_RUN_FLAG, "w").close()


def install_or_update_deps(log_cb=None):
    """
    Provision all runtime dependencies.

    Frozen app  → yt-dlp and yt-dlp-ejs are bundled inside the app;
                  ffmpeg is bundled via imageio-ffmpeg (PyInstaller).
                  Nothing needs to be downloaded on first run.
    Script mode → pip install / upgrade yt-dlp + imageio-ffmpeg + yt-dlp-ejs.

    Streams progress lines to log_cb(str).
    Returns a (possibly empty) list of error strings.
    """
    def log(msg):
        if log_cb:
            log_cb(msg)

    errors = []

    if getattr(sys, "frozen", False):
        # ── Frozen app ─────────────────────────────────────────────────────
        log("→ yt-dlp:        bundled inside the application  ✓\n")
        log("→ yt-dlp-ejs:    bundled inside the application  ✓\n")
        log("→ ffmpeg:        bundled inside the application via imageio-ffmpeg  ✓\n")
        log("\nAll dependencies are ready.\n")
    else:
        # ── Script mode ────────────────────────────────────────────────────
        for pkg in ("yt-dlp", "imageio-ffmpeg", "yt-dlp-ejs"):
            log(f"→ {pkg}: installing / updating …")
            try:
                proc = subprocess.Popen(
                    [sys.executable, "-m", "pip", "install", "--upgrade", pkg],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                )
                for line in proc.stdout:
                    s = line.strip()
                    if s:
                        log(f"  {s}")
                proc.wait()
                if proc.returncode == 0:
                    log(f"  ✓ {pkg} is ready\n")
                else:
                    errors.append(f"{pkg} exited with code {proc.returncode}")
                    log(f"  ✗ {pkg} install failed\n")
            except Exception as exc:
                errors.append(f"{pkg}: {exc}")
                log(f"  ✗ Exception: {exc}\n")

    return errors


# ─── First-Run Setup Dialog ───────────────────────────────────────────────────

def show_setup_dialog(parent, on_complete):
    """
    Modal setup window. Installs deps in a daemon thread, then fires
    on_complete() on the main thread once finished.
    Uses queue.Queue + polling so the background thread never touches tkinter.
    """
    W, H = 540, 410
    win = tk.Toplevel(parent)
    win.title("First-Time Setup")
    win.resizable(False, False)
    win.protocol("WM_DELETE_WINDOW", lambda: None)   # block manual close
    win.update_idletasks()
    win.geometry(
        f"{W}x{H}+{(win.winfo_screenwidth()  - W) // 2}"
        f"+{(win.winfo_screenheight() - H) // 2}"
    )

    ttk.Label(win, text="YouTube Downloader",
              font=("Segoe UI", 18, "bold"), foreground="#1976D2").pack(pady=(24, 2))
    ttk.Label(win, text="First-Time Setup — Installing dependencies",
              font=("Segoe UI", 11)).pack(pady=(0, 10))

    progress = ttk.Progressbar(win, mode="indeterminate", length=490)
    progress.pack(padx=20, pady=6)
    progress.start(12)

    log_box = tk.Text(win, height=11, font=("Consolas", 10),
                      state="disabled", bg="#f5f5f5", relief="flat", bd=1)
    log_box.pack(padx=20, pady=8, fill="both", expand=True)

    status_var = tk.StringVar(value="Starting…")
    ttk.Label(win, textvariable=status_var, font=("Segoe UI", 11)).pack(pady=(0, 12))

    log_q    = queue.Queue()   # background thread puts str messages here
    done_q   = queue.Queue()   # background thread puts result dict here

    def _append(msg):
        log_box.config(state="normal")
        log_box.insert(tk.END, msg + "\n")
        log_box.see(tk.END)
        log_box.config(state="disabled")

    def _poll():
        # Drain all pending log messages
        try:
            while True:
                msg = log_q.get_nowait()
                _append(msg)
        except queue.Empty:
            pass
        # Check if background work finished
        try:
            result = done_q.get_nowait()
            progress.stop()
            status_var.set(
                "Setup finished with warnings — see log above."
                if result["errors"] else "All done!  Launching the app…"
            )
            _append("\nOpening application…")
            win.after(1500, lambda: (win.destroy(), on_complete()))
            return   # stop polling
        except queue.Empty:
            pass
        win.after(50, _poll)   # keep polling every 50 ms

    def do_setup():
        errors = install_or_update_deps(log_q.put)
        mark_setup_done()
        done_q.put({"errors": errors})

    win.after(50, _poll)
    threading.Thread(target=do_setup, daemon=True).start()
    win.grab_set()


# ─── Main Application ─────────────────────────────────────────────────────────

class YTDownloaderApp:
    def __init__(self, root):
        self.root             = root
        self.download_process = None
        self._build_ui()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        r = self.root
        r.title("YouTube Downloader (yt-dlp GUI)")
        r.minsize(700, 520)
        r.geometry("920x680")

        try:
            r.iconphoto(True, tk.PhotoImage(file="icon.png"))
        except Exception:
            pass

        style = ttk.Style(r)
        style.theme_use("vista" if "vista" in style.theme_names() else "default")
        BIG    = ("Segoe UI", 15)
        HEADER = ("Segoe UI", 22, "bold")
        BOLD   = ("Segoe UI", 15, "bold")
        style.configure("TLabel",        font=BIG)
        style.configure("TButton",       font=BOLD, padding=8)
        style.configure("TEntry",        font=BIG)
        style.configure("TCombobox",     font=BIG)
        style.configure("Header.TLabel", font=HEADER, foreground="#1976D2")
        style.map("TCombobox",
                  fieldbackground=[("readonly", "#ffffff")],
                  selectbackground=[("readonly", "#1976D2")],
                  selectforeground=[("readonly", "#ffffff")])

        mf = ttk.Frame(r, padding=20)
        mf.grid(row=0, column=0, sticky="nsew")
        r.grid_rowconfigure(0, weight=1)
        r.grid_columnconfigure(0, weight=1)

        # ── Title ─────────────────────────────────────────────────────────────
        tf = ttk.Frame(mf)
        tf.grid(row=0, column=0, columnspan=3, pady=(0, 10), sticky="ew")
        ttk.Label(tf, text="YouTube Downloader",
                  style="Header.TLabel").pack(side="left", padx=(0, 8))
        ttk.Label(tf, text="🎬",
                  font=("Segoe UI Emoji", 22)).pack(side="left")
        ttk.Label(tf, text="powered by yt-dlp",
                  font=("Segoe UI", 13, "italic"),
                  foreground="#1976D2").pack(side="left", padx=(10, 0))

        tk.Frame(mf, bg="#1976D2", height=3).grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=(0, 16))

        # ── URL ───────────────────────────────────────────────────────────────
        ttk.Label(mf, text="Video / Playlist URL:").grid(
            row=2, column=0, sticky="e", pady=5)
        self.url_entry = ttk.Entry(mf, width=60)
        self.url_entry.grid(row=2, column=1, columnspan=2, sticky="ew", pady=5)
        mf.grid_columnconfigure(2, weight=1)

        # ── Cookies file ──────────────────────────────────────────────────────
        ttk.Label(mf, text="Cookies File (optional):").grid(
            row=3, column=0, sticky="e", pady=5)
        self.cookies_var = tk.StringVar()
        self.cookies_entry = ttk.Entry(mf, textvariable=self.cookies_var, width=45)
        self.cookies_entry.grid(row=3, column=1, sticky="ew", pady=5)
        ttk.Button(mf, text="Browse",
                   command=self.browse_cookies).grid(row=3, column=2, sticky="w", padx=5)

        # ── Browser cookies ───────────────────────────────────────────────────
        ttk.Label(mf, text="Select Browser:").grid(
            row=4, column=0, sticky="e", pady=5)
        self.browser_var = tk.BooleanVar()
        ttk.Checkbutton(mf, text="Use Browser Cookies",
                        variable=self.browser_var,
                        command=self._on_browser_toggle).grid(
            row=4, column=1, sticky="w", pady=5)
        self.browser_list = ttk.Combobox(
            mf, values=["None", "Chrome", "Brave", "Firefox", "Edge"],
            state="disabled", width=15)
        self.browser_list.current(0)
        self.browser_list.grid(row=4, column=2, sticky="w", pady=5)

        # ── Quality ───────────────────────────────────────────────────────────
        ttk.Label(mf, text="Select Quality:").grid(
            row=5, column=0, sticky="e", pady=5)
        self.quality_list = ttk.Combobox(
            mf,
            values=["Best", "Audio Only", "720p", "1080p", "1440p", "2160p", "4320p (8K)"],
            state="readonly", width=15)
        self.quality_list.current(0)
        self.quality_list.grid(row=5, column=1, sticky="w", pady=5)

        # ── Concurrent fragments ──────────────────────────────────────────────
        ttk.Label(mf, text="Connections (fragments):").grid(
            row=6, column=0, sticky="e", pady=5)
        self.conns_var = tk.IntVar(value=4)
        ttk.Spinbox(mf, from_=1, to=16, textvariable=self.conns_var,
                    width=5, state="readonly").grid(row=6, column=1, sticky="w", pady=5)

        # ── Playlist range ────────────────────────────────────────────────────
        ttk.Label(mf, text="Playlist Range (optional, e.g. 1-50):").grid(
            row=7, column=0, sticky="e", pady=5)
        self.playlist_range_entry = ttk.Entry(mf, width=20)
        self.playlist_range_entry.grid(row=7, column=1, sticky="w", pady=5)

        # ── Output directory ──────────────────────────────────────────────────
        ttk.Label(mf, text="Download Folder:").grid(
            row=8, column=0, sticky="e", pady=5)
        self.output_dir_var = tk.StringVar()
        self.output_dir_entry = ttk.Entry(mf, textvariable=self.output_dir_var, width=45)
        self.output_dir_entry.grid(row=8, column=1, sticky="ew", pady=5)
        ttk.Button(mf, text="Browse",
                   command=self.browse_folder).grid(row=8, column=2, sticky="w", padx=5)

        # ── Action buttons ────────────────────────────────────────────────────
        bf = ttk.Frame(mf)
        bf.grid(row=9, column=0, columnspan=3, pady=15)
        ttk.Button(bf, text="Download",
                   command=self.start_download).pack(side="left", padx=10)
        ttk.Button(bf, text="Stop",
                   command=self.stop_download).pack(side="left", padx=10)
        ttk.Button(bf, text="Check for Updates",
                   command=self.check_for_updates).pack(side="left", padx=10)

        # ── Progress bar ──────────────────────────────────────────────────────
        self.progress_bar = ttk.Progressbar(
            mf, orient="horizontal", length=400, mode="determinate")
        self.progress_bar.grid(row=10, column=0, columnspan=3, sticky="ew", pady=10)

        # ── Status label ──────────────────────────────────────────────────────
        self.status_label = ttk.Label(mf, text="", foreground="#388E3C",
                                      font=("Segoe UI", 15))
        self.status_label.grid(row=11, column=0, columnspan=3, sticky="w", pady=5)

        # ── Log area ──────────────────────────────────────────────────────────
        ttk.Label(mf, text="Logs",
                  font=("Segoe UI", 14, "bold")).grid(
            row=12, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.output_text = tk.Text(mf, height=12, width=80, font=("Consolas", 13))
        self.output_text.grid(row=13, column=0, columnspan=3, sticky="nsew", pady=10)
        mf.grid_rowconfigure(13, weight=1)

        # Context menus on all text inputs
        for w in (self.url_entry, self.cookies_entry,
                  self.output_dir_entry, self.playlist_range_entry,
                  self.output_text):
            self._add_ctx_menu(w)

        # Footer
        ttk.Label(r, text="Created by Pratik © 2026",
                  font=("Segoe UI", 11, "italic"),
                  foreground="#888").grid(row=1, column=0, sticky="sew", pady=(0, 8))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def browse_folder(self):
        d = filedialog.askdirectory(title="Select Download Folder")
        if d:
            self.output_dir_var.set(d)

    def browse_cookies(self):
        f = filedialog.askopenfilename(
            title="Select Cookies File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if f:
            self.cookies_var.set(f)

    def _on_browser_toggle(self):
        self.browser_list.config(
            state="readonly" if self.browser_var.get() else "disabled")

    def _show_ctx_menu(self, event, widget):
        m = tk.Menu(self.root, tearoff=0)
        for lbl, seq in (("Cut", "<<Cut>>"), ("Copy", "<<Copy>>"), ("Paste", "<<Paste>>")):
            m.add_command(label=lbl, command=lambda s=seq: widget.event_generate(s))
        m.add_separator()
        m.add_command(label="Select All",
                      command=lambda: widget.event_generate("<<SelectAll>>"))
        m.tk_popup(event.x_root, event.y_root)

    def _add_ctx_menu(self, widget):
        widget.bind("<Button-3>",         lambda e: self._show_ctx_menu(e, widget))
        widget.bind("<Control-Button-1>", lambda e: self._show_ctx_menu(e, widget))

    @staticmethod
    def _is_playlist(url):
        return "playlist" in url or "list=" in url

    # ── Download ──────────────────────────────────────────────────────────────

    def _ui(self, fn):
        """Thread-safe helper: schedule fn() on the Tk main-loop thread."""
        self.root.after(0, fn)

    def start_download(self):
        # Read all widget values NOW on the main thread, then hand off to thread.
        params = dict(
            url      = self.url_entry.get().strip(),
            cookies  = self.cookies_var.get().strip(),
            use_brws = self.browser_var.get(),
            browser  = self.browser_list.get(),
            out_dir  = self.output_dir_var.get().strip(),
            quality  = self.quality_list.get(),
            pl_range = self.playlist_range_entry.get().strip(),
            conns    = self.conns_var.get(),
        )
        threading.Thread(target=self._download, args=(params,), daemon=True).start()

    def stop_download(self):
        if self.download_process and self.download_process.poll() is None:
            self.download_process.terminate()
            self.status_label.config(text="Download stopped by user.")
        else:
            self.status_label.config(text="No active download to stop.")

    def _download(self, params):
        url      = params["url"]
        cookies  = params["cookies"]
        use_brws = params["use_brws"]
        browser  = params["browser"]
        out_dir  = params["out_dir"]
        quality  = params["quality"]
        pl_range = params["pl_range"]
        conns    = params["conns"]

        if not url:
            self._ui(lambda: self.status_label.config(text="URL is required!"))
            return
        if not out_dir:
            self._ui(lambda: self.status_label.config(text="Download folder is required!"))
            return

        ytdlp = get_ytdlp_cmd()
        if not ytdlp:
            self._ui(lambda: self.status_label.config(
                text="yt-dlp not found — click 'Check for Updates' to install it."))
            return

        ffmpeg = get_ffmpeg_path()
        if not ffmpeg:
            self._ui(lambda: self.status_label.config(
                text="ffmpeg not found — click 'Check for Updates' to install it."))
            return

        if self._is_playlist(url):
            tmpl = os.path.join(
                out_dir, "%(playlist_title)s",
                "%(playlist_index)s - %(title)s.%(ext)s")
        else:
            yt_dir = os.path.join(out_dir, "YT-Video")
            os.makedirs(yt_dir, exist_ok=True)
            tmpl = os.path.join(yt_dir, "%(title)s.%(ext)s")

        cmd = ytdlp + ["-o", tmpl, "--no-overwrites",
                      "--ffmpeg-location", ffmpeg]

        # Enable Node.js JS runtime if available (required by yt-dlp to solve
        # YouTube's signature/n-challenge; yt-dlp-ejs provides the solver scripts).
        # Search common install paths in addition to PATH for frozen apps,
        # which may have a restricted PATH that doesn't include the Node.js dir.
        _node_candidates = [
            # macOS — Homebrew
            "/opt/homebrew/bin/node",       # Apple Silicon
            "/usr/local/bin/node",          # Intel / nvm
            "/usr/bin/node",                # system
            # Windows
            r"C:\Program Files\nodejs\node.exe",
            r"C:\Program Files (x86)\nodejs\node.exe",
            # Linux
            "/usr/local/bin/node",
            "/usr/bin/nodejs",
        ]
        _node_path = shutil.which("node") or next(
            (p for p in _node_candidates if os.path.isfile(p) and os.access(p, os.X_OK)),
            None
        )
        if _node_path:
            cmd += ["--js-runtimes", f"node:{_node_path}"]

        quality_flags = {
            "Best":       ["-f", "bestvideo+bestaudio/best"],
            "Audio Only": ["-f", "bestaudio"],
            "720p":       ["-f", "bestvideo[height<=720]+bestaudio/best[height<=720]"],
            "1080p":      ["-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]"],
            "1440p":      ["-f", "bestvideo[height<=1440]+bestaudio/best[height<=1440]"],
            "2160p":      ["-f", "bestvideo[height<=2160]+bestaudio/best[height<=2160]"],
            "4320p (8K)": ["-f", "bestvideo[height<=4320]+bestaudio/best[height<=4320]"],
        }
        cmd += quality_flags.get(quality, [])

        cmd += ["--concurrent-fragments", str(conns)]

        if self._is_playlist(url):
            # Sleep 3–8 s between playlist items to avoid YouTube rate-limiting
            cmd += ["--sleep-interval", "3", "--max-sleep-interval", "8"]

        if pl_range:
            cmd += ["--playlist-items", pl_range]
        if use_brws and browser != "None":
            cmd += ["--cookies-from-browser", browser.lower()]
        elif cookies:
            cmd += ["--cookies", cookies]
        cmd += ["-ic", url]

        self._ui(lambda: self.status_label.config(text="Downloading…"))
        self._ui(lambda: self.output_text.delete(1.0, tk.END))

        try:
            self.download_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True)
            self._ui(lambda: self.progress_bar.configure(value=0))
            for line in self.download_process.stdout:
                ln = line
                self._ui(lambda l=ln: (
                    self.output_text.insert(tk.END, l),
                    self.output_text.see(tk.END)
                ))
                if "[download]" in line and "%" in line:
                    try:
                        pct = float(line.split("%")[0].split()[-1])
                        self._ui(lambda p=pct: self.progress_bar.configure(value=p))
                    except Exception:
                        pass
            self.download_process.wait()
            rc = self.download_process.returncode
            msg = ("Download complete!" if rc == 0
                   else "Download finished with errors or was stopped.")
            self._ui(lambda m=msg: self.status_label.config(text=m))
            self._ui(lambda: self.progress_bar.configure(value=0))
        except Exception as e:
            err = str(e)
            self._ui(lambda m=err: self.status_label.config(text=f"Error: {m}"))
        finally:
            self.download_process = None

    # ── Check for Updates ─────────────────────────────────────────────────────

    def check_for_updates(self):
        if getattr(sys, "frozen", False):
            self._frozen_update()
            return

        W, H = 540, 370
        win = tk.Toplevel(self.root)
        win.title("Check for Updates")
        win.resizable(False, False)
        win.grab_set()
        win.update_idletasks()
        win.geometry(
            f"{W}x{H}+{(win.winfo_screenwidth()  - W) // 2}"
            f"+{(win.winfo_screenheight() - H) // 2}"
        )

        ttk.Label(win, text="Updating Dependencies",
                  font=("Segoe UI", 16, "bold"),
                  foreground="#1976D2").pack(pady=(20, 5))

        progress = ttk.Progressbar(win, mode="indeterminate", length=490)
        progress.pack(padx=20, pady=8)
        progress.start(12)

        log_box = tk.Text(win, height=9, font=("Consolas", 10),
                          state="disabled", bg="#f5f5f5", relief="flat", bd=1)
        log_box.pack(padx=20, pady=8, fill="both", expand=True)

        status_var = tk.StringVar(value="Checking…")
        ttk.Label(win, textvariable=status_var, font=("Segoe UI", 11)).pack(pady=(0, 4))

        close_btn = ttk.Button(win, text="Close", command=win.destroy, state="disabled")
        close_btn.pack(pady=(0, 12))

        log_q  = queue.Queue()
        done_q = queue.Queue()

        def _append(msg):
            log_box.config(state="normal")
            log_box.insert(tk.END, msg + "\n")
            log_box.see(tk.END)
            log_box.config(state="disabled")

        def _poll():
            try:
                while True:
                    _append(log_q.get_nowait())
            except queue.Empty:
                pass
            try:
                result = done_q.get_nowait()
                progress.stop()
                status_var.set(
                    "Updated with warnings — see log." if result["errors"]
                    else "All dependencies are up to date!")
                close_btn.config(state="normal")
                return
            except queue.Empty:
                pass
            win.after(50, _poll)

        def do_update():
            errors = install_or_update_deps(log_q.put)
            done_q.put({"errors": errors})

        win.after(50, _poll)
        threading.Thread(target=do_update, daemon=True).start()

    def _frozen_update(self):
        """
        For PyInstaller builds: yt-dlp and yt-dlp-ejs are bundled inside the
        app, so there is nothing to update at runtime.  Inform the user to
        download the latest release of YTDownloader for dependency updates.
        """
        import tkinter.messagebox as mb
        mb.showinfo(
            "Check for Updates",
            "yt-dlp and all dependencies are bundled inside this application.\n\n"
            "To get the latest versions, please download the newest release of "
            "YTDownloader from GitHub:\n\n"
            "https://github.com/craftedbypratik/YT-Downloader-PS/releases",
            parent=self.root,
        )


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    root.withdraw()   # hide until setup (if any) finishes

    def launch():
        root.deiconify()
        YTDownloaderApp(root)

    # PyInstaller bundles already contain their deps — skip first-run setup
    if is_setup_done() or getattr(sys, "frozen", False):
        launch()
    else:
        show_setup_dialog(root, on_complete=launch)

    root.mainloop()


if __name__ == "__main__":
    main()

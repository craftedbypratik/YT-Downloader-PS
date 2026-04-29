import tkinter as tk
from tkinter import ttk, filedialog
import subprocess
import threading
import os
import sys
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
    Resolution order:
      1. ~/.yt-downloader/bin/  — binary downloaded at first-run (frozen app)
      2. system PATH            — yt-dlp installed globally or in active venv
      3. python -m yt_dlp       — pip-installed module (script mode fallback)
    Returns [] if nothing is found (triggers a setup reminder in the UI).
    """
    system   = platform.system()
    bin_name = _YTDLP_BIN.get(system, "yt-dlp")
    cached   = os.path.join(APP_BIN_DIR, bin_name)
    if os.path.isfile(cached) and os.access(cached, os.X_OK):
        return [cached]
    p = shutil.which("yt-dlp")
    if p:
        return [p]
    if not getattr(sys, "frozen", False):
        # Script mode: try running as an installed module
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

    Frozen app  → download yt-dlp binary to APP_BIN_DIR;
                  ffmpeg is already bundled (imageio_ffmpeg collected by PyInstaller).
    Script mode → pip install / upgrade yt-dlp + imageio-ffmpeg.

    Streams progress lines to log_cb(str).
    Returns a (possibly empty) list of error strings.
    """
    def log(msg):
        if log_cb:
            log_cb(msg)

    errors = []

    if getattr(sys, "frozen", False):
        # ── Frozen app ─────────────────────────────────────────────────────
        log("→ ffmpeg: bundled inside the application via imageio-ffmpeg  ✓\n")
        ok = download_ytdlp_binary(log_cb)
        if not ok:
            errors.append("yt-dlp binary download failed")
    else:
        # ── Script mode ────────────────────────────────────────────────────
        for pkg in ("yt-dlp", "imageio-ffmpeg"):
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
    Modal setup window.  Installs deps in a daemon thread, then fires
    on_complete() on the main thread once finished.
    All UI updates from the background thread are marshalled via win.after().
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

    def _append_direct(msg):
        """Must only be called on the main thread."""
        log_box.config(state="normal")
        log_box.insert(tk.END, msg + "\n")
        log_box.see(tk.END)
        log_box.config(state="disabled")

    def append(msg):
        """Thread-safe: schedules the UI update on the main thread."""
        win.after(0, lambda m=msg: _append_direct(m))

    def do_setup():
        errors = install_or_update_deps(append)
        mark_setup_done()
        if errors:
            win.after(0, lambda: status_var.set("Setup finished with warnings — see log above."))
        else:
            win.after(0, lambda: status_var.set("All done!  Launching the app…"))
        win.after(0, lambda: _append_direct("\nOpening application…"))
        win.after(0, progress.stop)


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
            values=["Best", "Audio Only", "720p", "1080p", "1440p", "2160p"],
            state="readonly", width=15)
        self.quality_list.current(0)
        self.quality_list.grid(row=5, column=1, sticky="w", pady=5)

        # ── Playlist range ────────────────────────────────────────────────────
        ttk.Label(mf, text="Playlist Range (optional, e.g. 1-50):").grid(
            row=6, column=0, sticky="e", pady=5)
        self.playlist_range_entry = ttk.Entry(mf, width=20)
        self.playlist_range_entry.grid(row=6, column=1, sticky="w", pady=5)

        # ── Output directory ──────────────────────────────────────────────────
        ttk.Label(mf, text="Download Folder:").grid(
            row=7, column=0, sticky="e", pady=5)
        self.output_dir_var = tk.StringVar()
        self.output_dir_entry = ttk.Entry(mf, textvariable=self.output_dir_var, width=45)
        self.output_dir_entry.grid(row=7, column=1, sticky="ew", pady=5)
        ttk.Button(mf, text="Browse",
                   command=self.browse_folder).grid(row=7, column=2, sticky="w", padx=5)

        # ── Action buttons ────────────────────────────────────────────────────
        bf = ttk.Frame(mf)
        bf.grid(row=8, column=0, columnspan=3, pady=15)
        ttk.Button(bf, text="Download",
                   command=self.start_download).pack(side="left", padx=10)
        ttk.Button(bf, text="Stop",
                   command=self.stop_download).pack(side="left", padx=10)
        ttk.Button(bf, text="Check for Updates",
                   command=self.check_for_updates).pack(side="left", padx=10)

        # ── Progress bar ──────────────────────────────────────────────────────
        self.progress_bar = ttk.Progressbar(
            mf, orient="horizontal", length=400, mode="determinate")
        self.progress_bar.grid(row=9, column=0, columnspan=3, sticky="ew", pady=10)

        # ── Status label ──────────────────────────────────────────────────────
        self.status_label = ttk.Label(mf, text="", foreground="#388E3C",
                                      font=("Segoe UI", 15))
        self.status_label.grid(row=10, column=0, columnspan=3, sticky="w", pady=5)

        # ── Log area ──────────────────────────────────────────────────────────
        ttk.Label(mf, text="Logs",
                  font=("Segoe UI", 14, "bold")).grid(
            row=11, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.output_text = tk.Text(mf, height=12, width=80, font=("Consolas", 13))
        self.output_text.grid(row=12, column=0, columnspan=3, sticky="nsew", pady=10)
        mf.grid_rowconfigure(12, weight=1)

        # Context menus on all text inputs
        for w in (self.url_entry, self.cookies_entry,
                  self.output_dir_entry, self.playlist_range_entry,
                  self.output_text):
            self._add_ctx_menu(w)

        # Footer
        ttk.Label(r, text="Created by Pratik © 2025",
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

        quality_flags = {
            "Best":       ["-f", "bestvideo+bestaudio/best"],
            "Audio Only": ["-f", "bestaudio"],
            "720p":       ["-f", "best[height<=720]"],
            "1080p":      ["-f", "best[height<=1080]"],
            "1440p":      ["-f", "best[height<=1440]"],
            "2160p":      ["-f", "best[height<=2160]"],
        }
        cmd += quality_flags.get(quality, [])

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

        def _append_direct(msg):
            log_box.config(state="normal")
            log_box.insert(tk.END, msg + "\n")
            log_box.see(tk.END)
            log_box.config(state="disabled")

        def append(msg):
            win.after(0, lambda m=msg: _append_direct(m))

        def do_update():
            errors = install_or_update_deps(append)
            win.after(0, progress.stop)
            win.after(0, lambda: status_var.set(
                "Updated with warnings — see log." if errors
                else "All dependencies are up to date!"))
            win.after(0, lambda: close_btn.config(state="normal"))

        threading.Thread(target=do_update, daemon=True).start()

    def _frozen_update(self):
        """
        For PyInstaller builds: re-download the latest yt-dlp binary from
        GitHub releases into APP_BIN_DIR.  ffmpeg is bundled in the app and
        updates only when the user installs a newer build of the app.
        """
        W, H = 540, 320
        win = tk.Toplevel(self.root)
        win.title("Check for Updates")
        win.resizable(False, False)
        win.grab_set()
        win.update_idletasks()
        win.geometry(
            f"{W}x{H}+{(win.winfo_screenwidth()  - W) // 2}"
            f"+{(win.winfo_screenheight() - H) // 2}"
        )

        ttk.Label(win, text="Updating yt-dlp",
                  font=("Segoe UI", 16, "bold"),
                  foreground="#1976D2").pack(pady=(20, 5))

        progress = ttk.Progressbar(win, mode="indeterminate", length=490)
        progress.pack(padx=20, pady=8)
        progress.start(12)

        log_box = tk.Text(win, height=6, font=("Consolas", 10),
                          state="disabled", bg="#f5f5f5", relief="flat", bd=1)
        log_box.pack(padx=20, pady=8, fill="both", expand=True)

        status_var = tk.StringVar(value="Downloading…")
        ttk.Label(win, textvariable=status_var,
                  font=("Segoe UI", 11)).pack(pady=(0, 4))

        close_btn = ttk.Button(win, text="Close", command=win.destroy,
                               state="disabled")
        close_btn.pack(pady=(0, 12))

        def _append_direct(msg):
            log_box.config(state="normal")
            log_box.insert(tk.END, msg + "\n")
            log_box.see(tk.END)
            log_box.config(state="disabled")

        def append(msg):
            win.after(0, lambda m=msg: _append_direct(m))

        def do():
            ok = download_ytdlp_binary(append)
            win.after(0, progress.stop)
            win.after(0, lambda: status_var.set(
                "yt-dlp updated to the latest version!" if ok
                else "Update failed — check log above."))
            win.after(0, lambda: close_btn.config(state="normal"))

        threading.Thread(target=do, daemon=True).start()


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

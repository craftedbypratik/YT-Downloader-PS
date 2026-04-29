# -*- mode: python ; coding: utf-8 -*-
# Cross-platform PyInstaller spec for YTDownloader.
#
# All dependencies are bundled automatically:
#   ffmpeg    → imageio-ffmpeg pip package (pre-built binary per platform)
#   yt-dlp    → bundled as a Python module; frozen app re-invokes itself with
#               the '__ytdlp__' sentinel to run yt-dlp in-process, giving
#               access to yt-dlp-ejs for YouTube JS-challenge solving.
#   yt-dlp-ejs → bundled Python package + JS solver scripts
#
# Prerequisites (run once before building):
#   pip install pyinstaller imageio-ffmpeg yt-dlp yt-dlp-ejs

import os as _os
import platform as _platform
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

_system = _platform.system()
_icon   = {"Darwin": "icon.icns", "Windows": "icon.ico"}.get(_system)

# Collect data files from bundled packages
_imageio_datas = collect_data_files("imageio_ffmpeg", include_py_files=False)
_ejs_datas     = collect_data_files("yt_dlp_ejs",    include_py_files=False)
_ytdlp_datas   = collect_data_files("yt_dlp",        include_py_files=False)

# Icon datas — only include those that exist
_icon_datas = []
for _ico in ("icon.icns", "icon.ico"):
    if _os.path.isfile(_ico):
        _icon_datas.append((_ico, "."))

a = Analysis(
    ["yt_gui.py"],
    pathex=[],
    binaries=[],
    datas=_imageio_datas + _ejs_datas + _ytdlp_datas + _icon_datas,
    hiddenimports=[
        "imageio_ffmpeg",
        "yt_dlp",
        "yt_dlp_ejs",
        "yt_dlp_ejs.yt.solver",
    ] + collect_submodules("yt_dlp"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],                       # binaries excluded here for onedir mode
    exclude_binaries=True,
    name="YTDownloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="YTDownloader",
)

if _system == "Darwin":
    app = BUNDLE(
        coll,
        name="YTDownloader.app",
        icon=_icon,
        bundle_identifier="com.pratik.ytdownloader",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "2.0.0",
        },
    )

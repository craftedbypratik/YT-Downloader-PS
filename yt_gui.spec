# -*- mode: python ; coding: utf-8 -*-
# Cross-platform PyInstaller spec for YTDownloader.
#
# NO manual binaries are required.
#
# ffmpeg  → bundled automatically from the imageio-ffmpeg pip package.
#           Ensure imageio-ffmpeg is installed in your build environment:
#               pip install imageio-ffmpeg
#           PyInstaller will collect its pre-built ffmpeg binary via
#           collect_data_files('imageio_ffmpeg').
#
# yt-dlp  → downloaded from GitHub releases on first app launch and cached
#           in ~/.yt-downloader/bin/.  Nothing to do at build time.

import platform as _platform
from PyInstaller.utils.hooks import collect_data_files

_system = _platform.system()
_icon   = {"Darwin": "icon.icns", "Windows": "icon.ico"}.get(_system)

# Collect imageio_ffmpeg's pre-built ffmpeg binary + package data
_imageio_datas = collect_data_files("imageio_ffmpeg", include_py_files=False)

a = Analysis(
    ["yt_gui.py"],
    pathex=[],
    binaries=[],                          # no manual binaries needed
    datas=_imageio_datas + [
        ("icon.icns", "."),
        ("icon.ico",  "."),
    ],
    hiddenimports=["imageio_ffmpeg"],
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
    a.binaries,
    a.datas,
    [],
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

if _system == "Darwin":
    app = BUNDLE(
        exe,
        name="YTDownloader.app",
        icon=_icon,
        bundle_identifier="com.pratik.ytdownloader",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "2.0.0",
        },
    )

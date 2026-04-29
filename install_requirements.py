import os
import sys
import subprocess
import platform
import shutil

def run(cmd, shell=False):
    print(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    try:
        subprocess.check_call(cmd, shell=shell)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")

def install_pip_package(package):
    run([sys.executable, "-m", "pip", "install", "--upgrade", package])

def install_ffmpeg_windows():
    if shutil.which("choco"):
        run(["choco", "install", "-y", "ffmpeg"])
    elif shutil.which("winget"):
        run(["winget", "install", "-e", "--id", "Gyan.FFmpeg"])
    else:
        print("Please install ffmpeg manually from https://www.gyan.dev/ffmpeg/builds/ and add it to your PATH.")

def install_ffmpeg_mac():
    if shutil.which("brew"):
        run(["brew", "install", "ffmpeg"])
    else:
        print("Please install Homebrew from https://brew.sh/ and then run 'brew install ffmpeg'.")

def install_ffmpeg_linux():
    if shutil.which("apt"):
        run(["sudo", "apt", "update"])
        run(["sudo", "apt", "install", "-y", "ffmpeg"])
    elif shutil.which("dnf"):
        run(["sudo", "dnf", "install", "-y", "ffmpeg"])
    elif shutil.which("pacman"):
        run(["sudo", "pacman", "-Sy", "ffmpeg"])
    else:
        print("Please install ffmpeg using your distribution's package manager.")

def install_mac_certificates():
    pyver = f"{sys.version_info.major}.{sys.version_info.minor}"
    cert_cmd = f"/Applications/Python\\ {pyver}/Install\\ Certificates.command"
    if os.path.exists(cert_cmd):
        print("Running macOS certificates installer...")
        run([cert_cmd], shell=True)
    else:
        print("If you get SSL errors, run the 'Install Certificates.command' in your Python folder.")

def check_tkinter():
    try:
        import tkinter
        print("Tkinter is installed.")
    except ImportError:
        print("Tkinter is NOT installed. Please install it with your package manager or Python installer.")

def main():
    print("Checking for Tkinter...")
    check_tkinter()

    print("Installing yt-dlp...")
    install_pip_package("yt-dlp")

    print("Installing certifi (for SSL certificates)...")
    install_pip_package("certifi")

    print("Installing imageio-ffmpeg (cross-platform ffmpeg binary)...")
    install_pip_package("imageio-ffmpeg")

    system = platform.system()
    print(f"Detected OS: {system}")

    # Optional: also install a system-level ffmpeg if a package manager is available.
    # The app will use imageio-ffmpeg automatically, so this is only for users who
    # want ffmpeg available system-wide.
    if system == "Windows":
        print("(Optional) Installing system ffmpeg for Windows...")
        install_ffmpeg_windows()
    elif system == "Darwin":
        print("(Optional) Installing system ffmpeg for macOS...")
        install_ffmpeg_mac()
        install_mac_certificates()
    elif system == "Linux":
        print("(Optional) Installing system ffmpeg for Linux...")
        install_ffmpeg_linux()
    else:
        print("Unknown OS. imageio-ffmpeg will be used as the ffmpeg provider.")

    print("\nAll done!")
    print("You can now run your YouTube Downloader app (python yt_gui.py).")
    print("On first launch the app will verify all dependencies automatically.")

if __name__ == "__main__":
    main()
"""Screenshot capture — cross-platform screen capture.
Linux: uses scrot, gnome-screenshot, or xdotool as fallback
macOS: uses screencapture
Windows: uses ctypes/ctypes.wintypes for GDI capture"""

import os
import sys
import subprocess
import tempfile
import base64
from typing import Optional


def capture_screenshot(output_path: str = None) -> str:
    """Capture a screenshot and return the file path.

    Returns the path to the captured image, or raises an error.
    """
    if output_path is None:
        output_path = os.path.join(
            tempfile.gettempdir(), f"screencap_{os.getpid()}.png"
        )

    if sys.platform == "darwin":
        return _capture_macos(output_path)
    elif sys.platform == "win32":
        return _capture_windows(output_path)
    else:
        return _capture_linux(output_path)


def _capture_macos(output_path: str) -> str:
    result = subprocess.run(
        ["screencapture", "-x", output_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"screencapture failed: {result.stderr}")
    return output_path


def _capture_linux(output_path: str) -> str:
    # Try scrot first (most common)
    for cmd in [
        ["scrot", "-z", output_path],
        ["gnome-screenshot", "-f", output_path],
        ["import", "-window", "root", output_path],  # ImageMagick
    ]:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
        except FileNotFoundError:
            continue

    raise RuntimeError("No screenshot tool found (install scrot or imagemagick)")


def _capture_windows(output_path: str) -> str:
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        hdc_screen = user32.GetDC(0)
        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)

        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
        gdi32.SelectObject(hdc_mem, hbmp)
        gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, 0, 0, 0x00CC0020)

        # Use Pillow to save the bitmap
        import ctypes.wintypes
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = width
        bmi.biHeight = -height  # top-down
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0  # BI_RGB

        buf_size = width * height * 4
        buf = ctypes.create_string_buffer(buf_size)

        gdi32.GetDIBits(hdc_screen, hbmp, 0, height, buf, ctypes.byref(bmi), 0)

        try:
            from PIL import Image
            img = Image.frombytes("RGBA", (width, height), buf, "raw", "BGRA")
            img.save(output_path, "PNG")
        except ImportError:
            # Write raw BMP as fallback (not ideal but works without Pillow)
            with open(output_path, "wb") as f:
                f.write(buf)

        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)

        return output_path

    except Exception as e:
        raise RuntimeError(f"Windows screenshot failed: {e}")


def encode_base64(filepath: str) -> str:
    """Read and base64-encode a file for transmission."""
    with open(filepath, "rb") as f:
        return base64.b64encode(f.read()).decode()


def run(args: list[str]) -> str:
    """Module entry point. Usage: screenshot [output_path]"""
    output_path = args[0] if args else None

    try:
        path = capture_screenshot(output_path)
        size_kb = os.path.getsize(path) / 1024
        return f"Screenshot saved: {path} ({size_kb:.1f} KB)"
    except Exception as e:
        return f"Screenshot failed: {e}"

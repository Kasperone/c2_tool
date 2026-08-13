"""Webcam capture module — grabs screenshots from the system camera.

Usage:
    webcam capture [output_path]   # Take a photo (PNG format)
    webcam record [seconds] [output_path]  # Record video (MP4, requires ffmpeg)
    webcam list                    # List available cameras
"""

import os
import sys
import subprocess
import time
from typing import Optional


def run(args: list[str]) -> str:
    """Module entry point. Usage: webcam [capture|record|list] [args...]"""
    if not args:
        return "Usage: webcam [capture|record|list] [args...]"

    action = args[0].lower()

    if action == "capture":
        output_path = args[1] if len(args) > 1 else f"screenshot_{int(time.time())}.png"
        return _capture_photo(output_path)

    elif action == "record":
        duration = int(args[1]) if len(args) > 1 else 5
        output_path = args[2] if len(args) > 2 else f"recording_{int(time.time())}.mp4"
        return _record_video(duration, output_path)

    elif action == "list":
        return _list_cameras()

    return f"Unknown action: {action}\nUsage: webcam [capture|record|list] [args...]"


def _run_cmd(cmd: list[str] | str, shell: bool = False) -> str:
    """Run a command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            cmd, shell=shell, capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _list_cameras() -> str:
    """List available camera devices."""
    lines = []

    if sys.platform == "linux":
        # Try to find cameras via v4l2
        v4l2_list = _run_cmd("ls /dev/video* 2>/dev/null", shell=True)
        if v4l2_list:
            lines.append("Available cameras:")
            for cam in v4l2_list.split("\n"):
                cam = cam.strip()
                if cam:
                    # Try to get device info
                    info = _run_cmd(f"v4l2-ctl --device={cam} --info 2>/dev/null", shell=True)
                    lines.append(f"  {cam}" + (f" ({info.split(chr(10))[0]})" if info else ""))
        else:
            # Try fswebcam
            fswebcam_list = _run_cmd("fswebcam --list-devices 2>&1", shell=True)
            if fswebcam_list:
                lines.append("Available cameras:")
                for line in fswebcam_list.split("\n"):
                    if "at" in line or "found" in line:
                        lines.append(f"  {line.strip()}")

        if not lines:
            lines.append("No cameras detected on /dev/video*")

    elif sys.platform == "darwin":
        # macOS: use IOKit to list cameras
        iokit_list = _run_cmd(
            "ioreg -rd1 -c IovideoCamera 2>/dev/null", shell=True
        )
        if iokit_list and "IOVideoDevice" in iokit_list:
            lines.append("Available cameras:")
            for line in iokit_list.split("\n"):
                if "IOName" in line:
                    lines.append(f"  {line.strip()}")
        else:
            # Default to FaceTime camera
            lines.append("Default: Built-in FaceTime Camera")

    elif sys.platform == "win32":
        # Windows: use DirectShow via ffmpeg
        ffdevices = _run_cmd(
            'ffmpeg -list_devices true -f dshow -i dummy 2>&1', shell=True
        )
        if ffdevices and "DirectShow" in ffdevices:
            lines.append("Available cameras:")
            for line in ffdevices.split("\n"):
                if "DirectShow" in line or "capture" in line.lower():
                    lines.append(f"  {line.strip()}")
        else:
            lines.append("No cameras detected via DirectShow")

    return "\n".join(lines) if lines else "Camera detection failed"


def _capture_photo(output_path: str) -> str:
    """Capture a single photo from the webcam."""
    if sys.platform == "linux":
        # Try fswebcam first (lightweight)
        fswebcam_result = _run_cmd(
            f"fswebcam -r 1280x720 --no-banner {output_path} 2>&1", shell=True
        )
        if os.path.exists(output_path):
            return f"Photo captured: {output_path} ({_file_size(output_path)})"

        # Fallback: v4l2-ctl + ffmpeg
        v4l_result = _run_cmd(
            f"v4l2-ctl --device=/dev/video0 --stream-mmap=3 --stream-to={output_path} --stream-count=1 2>&1",
            shell=True
        )
        if os.path.exists(output_path):
            return f"Photo captured: {output_path} ({_file_size(output_path)})"

        return "Webcam capture failed on Linux (need fswebcam or v4l2-utils)"

    elif sys.platform == "darwin":
        # macOS: use screenshot utility or OpenCV
        import importlib
        try:
            from PIL import Image
            import numpy as np
        except ImportError:
            return "Webcam capture requires numpy (pip install numpy)"

        # Try to capture using imageio or OpenCV as fallback
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    cv2.imwrite(output_path, frame)
                    cap.release()
                    return f"Photo captured: {output_path} ({_file_size(output_path)})"
                cap.release()
        except (ImportError, Exception):
            pass

        return "Webcam capture failed on macOS (need opencv-python for camera access)"

    elif sys.platform == "win32":
        # Windows: try DirectShow via ffmpeg
        ff_result = _run_cmd(
            f'ffmpeg -f dshow -i video="Integrated Camera" -frames:v 1 -y {output_path} 2>&1',
            shell=True
        )
        if os.path.exists(output_path):
            return f"Photo captured: {output_path} ({_file_size(output_path)})"

        # Fallback: use pyautogui if available (limited)
        try:
            from PIL import Image
            # This won't work without a camera library, but try alternative
            return "Webcam capture requires a camera library (pip install imageio[ffmpeg])"
        except ImportError:
            pass

        return "Webcam capture failed on Windows (need ffmpeg with dshow support)"

    return "Webcam capture not supported on this platform"


def _record_video(duration: int, output_path: str) -> str:
    """Record video from the webcam for specified duration."""
    if not _check_ffmpeg():
        return "ffmpeg required for video recording. Install ffmpeg and try again."

    if sys.platform == "linux":
        # Try to find first available camera
        camera = _find_linux_camera()
        if not camera:
            return "No camera device found (/dev/video0)"
        cmd = f"ffmpeg -f v4l2 -i {camera} -t {duration} -y {output_path} 2>&1"
    elif sys.platform == "darwin":
        cmd = f"ffmpeg -f avfoundation -i ':0' -t {duration} -y {output_path} 2>&1"
    elif sys.platform == "win32":
        cmd = (
            f'ffmpeg -f dshow -i video="Integrated Camera" '
            f"-t {duration} -y {output_path} 2>&1"
        )
    else:
        return "Video recording not supported on this platform"

    result = _run_cmd(cmd, shell=True)
    if os.path.exists(output_path):
        return f"Recording saved: {output_path} ({_file_size(output_path)})"
    return "Video recording failed"


def _find_linux_camera() -> Optional[str]:
    """Find the first available video device on Linux."""
    if os.path.exists("/dev/video0"):
        return "/dev/video0"
    # Check for other devices
    for i in range(1, 10):
        path = f"/dev/video{i}"
        if os.path.exists(path):
            return path
    return None


def _check_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    return _run_cmd("ffmpeg -version") != ""


def _file_size(filepath: str) -> str:
    """Return human-readable file size."""
    if not os.path.exists(filepath):
        return "unknown"
    size_bytes = os.path.getsize(filepath)
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

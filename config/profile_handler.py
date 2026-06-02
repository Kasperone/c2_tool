import os
import yaml
import random
import string
from urllib.parse import quote
from typing import Optional


def load_profile(profile_name: Optional[str] = None) -> Optional[dict]:
    """Load a C2 profile from config/profiles/<name>.yaml"""
    if profile_name is None:
        profile_name = os.environ.get("C2_PROFILE")

    if profile_name is None:
        return None

    profile_dir = os.path.join(os.path.dirname(__file__), "profiles")
    profile_path = os.path.join(profile_dir, f"{profile_name}.yaml")

    if not os.path.exists(profile_path):
        raise FileNotFoundError(f"Profile not found: {profile_path}")

    with open(profile_path) as f:
        return yaml.safe_load(f)


def rotate_user_agent(profile: Optional[dict]) -> str:
    if not profile:
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    request = profile.get("http", {}).get("request", {})
    ua_rotation = request.get("user_agent_rotation", {})

    if ua_rotation.get("enabled") and ua_rotation.get("list"):
        return random.choice(ua_rotation["list"])

    return request.get("headers", {}).get("User-Agent", "Mozilla/5.0")


def rotate_accept_language(profile: Optional[dict]) -> str:
    if not profile:
        return "en-US,en;q=0.9"

    request = profile.get("http", {}).get("request", {})
    lang_rotation = request.get("accept_language_rotation", {})

    if lang_rotation.get("enabled") and lang_rotation.get("list"):
        return random.choice(lang_rotation["list"])

    return request.get("headers", {}).get("Accept-Language", "en-US,en;q=0.9")


def rotate_referer(profile: Optional[dict]) -> str:
    if not profile:
        return ""

    request = profile.get("http", {}).get("request", {})
    ref_rotation = request.get("referer_rotation", {})

    if ref_rotation.get("enabled") and ref_rotation.get("list"):
        return random.choice(ref_rotation["list"])

    return request.get("headers", {}).get("Referer", "")


def random_suffix(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def build_request_headers(profile: Optional[dict], request_type: str = "request") -> dict:
    """Build headers for a request type with rotation applied."""
    if not profile:
        from config import load_config
        cfg = load_config()
        return {"User-Agent": cfg.http.user_agent}

    http = profile.get("http", {})
    req_config = http.get(request_type, {})
    headers = dict(req_config.get("headers", {}))

    if request_type == "request":
        if "User-Agent" in headers and http.get("request", {}).get("user_agent_rotation", {}).get("enabled"):
            headers["User-Agent"] = rotate_user_agent(profile)
        if "Accept-Language" in headers and http.get("request", {}).get("accept_language_rotation", {}).get("enabled"):
            headers["Accept-Language"] = rotate_accept_language(profile)
        if "Referer" in headers and http.get("request", {}).get("referer_rotation", {}).get("enabled"):
            headers["Referer"] = rotate_referer(profile)

    return headers


def build_uri(profile: Optional[dict], request_type: str = "request", append: Optional[str] = None) -> str:
    """Build URI for a request type with optional random suffix and data append."""
    if not profile:
        from config import load_config
        cfg = load_config()
        path_map = {
            "request": cfg.http.cmd_request_path,
            "file_request": cfg.http.file_request_path,
            "file_upload": cfg.http.file_upload_path,
            "response": cfg.http.response_path,
            "cwd_response": cfg.http.cwd_response_path,
        }
        uri = path_map.get(request_type, "/")
        if append is not None:
            uri = f"{uri}{quote(append, safe='')}"
        return uri

    http = profile.get("http", {})
    req_config = http.get(request_type, {})
    uri = req_config.get("uri_pattern", "/")

    if req_config.get("uri_random_suffix"):
        separator = "&" if "?" in uri else "?"
        uri = f"{uri}{separator}v={random_suffix(6)}"

    if append is not None:
        if "?" in uri:
            uri = f"{uri}&data={quote(append, safe='')}"
        else:
            uri = f"{uri}?data={quote(append, safe='')}"

    return uri

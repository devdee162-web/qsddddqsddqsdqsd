"""Client HTTP vers l'API Discord hebergee sur la VM (+ repli SMB)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_STATUS_CACHE: tuple[float, dict | None] | None = None
_TOKEN_CACHE: tuple[float, str] | None = None
_CACHE_TTL = 45
_LAST_ERROR = ""


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def last_api_error() -> str:
    return _LAST_ERROR


def _set_error(message: str) -> None:
    global _LAST_ERROR
    _LAST_ERROR = message


def _api_port() -> str:
    return os.getenv("DISCORD_API_PORT", "8780").strip() or "8780"


def resolve_discord_api_urls() -> list[str]:
    port = _api_port()
    urls: list[str] = []

    explicit = os.getenv("DISCORD_API_URL", "").strip().rstrip("/")
    if explicit:
        urls.append(explicit)

    if _truthy(os.getenv("DISCORD_API_ENABLED", "true")):
        host = os.getenv("SYNC_VM_HOST", "").strip()
        if host:
            urls.append(f"http://{host}:{port}")
        for local_host in ("127.0.0.1", "localhost"):
            urls.append(f"http://{local_host}:{port}")

    unique: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def resolve_discord_api_url() -> str:
    urls = resolve_discord_api_urls()
    return urls[0] if urls else ""


def discord_api_key() -> str:
    return os.getenv("DISCORD_API_KEY", "").strip()


def discord_api_configured() -> bool:
    if resolve_discord_api_url():
        return True
    return bool(os.getenv("SYNC_VM_HOST", "").strip())


def _parse_env_text(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _vm_share_unc() -> str:
    host = os.getenv("SYNC_VM_HOST", "").strip()
    if not host:
        return ""
    share = os.getenv("SYNC_VM_SHARE", "tool_oap").strip() or "tool_oap"
    return f"\\\\{host}\\{share}"


def _ensure_vm_share_connected() -> bool:
    unc = _vm_share_unc()
    if not unc or sys.platform != "win32":
        return False

    if Path(unc).exists():
        return True

    user = os.getenv("SYNC_VM_USER", "").strip()
    password = os.getenv("SYNC_VM_PASS", "").strip()
    if not user or not password:
        return False

    creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    result = subprocess.run(
        ["net", "use", unc, password, f"/user:{user}", "/persistent:no"],
        capture_output=True,
        text=True,
        creationflags=creationflags,
    )
    output = f"{result.stdout}\n{result.stderr}".lower()
    if result.returncode == 0 or "deja" in output or "already" in output or "1219" in output:
        return Path(unc).exists()
    return False


def _share_paths() -> list[Path]:
    unc = _vm_share_unc()
    if not unc:
        return []
    root = Path(unc)
    return [
        root / "discord_api.env",
        root / "discord_api" / "discord_api.env",
        root / "discord_status.json",
        root / "discord_api" / "discord_status.json",
    ]


def _read_share_env() -> dict[str, str]:
    if not _ensure_vm_share_connected():
        return {}

    for path in _share_paths():
        if path.name != "discord_api.env" or not path.exists():
            continue
        try:
            return _parse_env_text(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return {}


def _read_share_status() -> dict | None:
    if not _ensure_vm_share_connected():
        return None

    for path in _share_paths():
        if path.name != "discord_status.json" or not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            continue
    return None


def _http_request(url: str, path: str, *, timeout: float) -> dict | None:
    request = urllib.request.Request(f"{url.rstrip('/')}{path}")
    key = discord_api_key()
    if key:
        request.add_header("X-API-Key", key)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8", errors="replace")
            data = json.loads(payload)
            return data if isinstance(data, dict) else None
    except urllib.error.HTTPError as exc:
        _set_error(f"HTTP {exc.code} sur {url}")
        return None
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        _set_error(f"{url} injoignable ({reason})")
        return None
    except (TimeoutError, json.JSONDecodeError, OSError) as exc:
        _set_error(f"{url} erreur ({exc})")
        return None


def _api_request(path: str, *, timeout: float = 10.0) -> dict | None:
    for url in resolve_discord_api_urls():
        data = _http_request(url, path, timeout=timeout)
        if data is not None:
            _set_error("")
            return data
    return None


def fetch_discord_status(*, force: bool = False) -> dict | None:
    global _STATUS_CACHE
    now = time.time()
    if not force and _STATUS_CACHE and now - _STATUS_CACHE[0] < _CACHE_TTL:
        return _STATUS_CACHE[1]

    data = _api_request("/api/discord/status")
    if data is None:
        data = _read_share_status()
        if data is None:
            share_env = _read_share_env()
            if share_env.get("DISCORD_TOKEN"):
                data = {"configured": True, "bot_username": "", "source": "smb"}

    _STATUS_CACHE = (now, data)
    return data


def fetch_discord_token(*, force: bool = False) -> str:
    global _TOKEN_CACHE
    now = time.time()
    if not force and _TOKEN_CACHE and now - _TOKEN_CACHE[0] < _CACHE_TTL:
        return _TOKEN_CACHE[1]

    token = ""
    data = _api_request("/api/discord/token")
    if data and isinstance(data.get("token"), str):
        token = data["token"].strip()
    if not token:
        share_env = _read_share_env()
        token = share_env.get("DISCORD_TOKEN", "").strip()

    _TOKEN_CACHE = (now, token)
    return token


def clear_discord_api_cache() -> None:
    global _STATUS_CACHE, _TOKEN_CACHE
    _STATUS_CACHE = None
    _TOKEN_CACHE = None
    _set_error("")

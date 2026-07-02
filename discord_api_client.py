"""Client HTTP vers l'API Discord hebergee sur la VM."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

_STATUS_CACHE: tuple[float, dict | None] | None = None
_TOKEN_CACHE: tuple[float, str] | None = None
CACHE_TTL = 45


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def resolve_discord_api_url() -> str:
    explicit = os.getenv("DISCORD_API_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    if not _truthy(os.getenv("DISCORD_API_ENABLED", "true")):
        return ""
    host = os.getenv("SYNC_VM_HOST", "").strip()
    if not host:
        return ""
    port = os.getenv("DISCORD_API_PORT", "8780").strip() or "8780"
    return f"http://{host}:{port}"


def discord_api_key() -> str:
    return os.getenv("DISCORD_API_KEY", "").strip()


def discord_api_configured() -> bool:
    return bool(resolve_discord_api_url())


def _api_request(path: str, *, timeout: float = 6.0) -> dict | None:
    base = resolve_discord_api_url()
    if not base:
        return None

    request = urllib.request.Request(f"{base}{path}")
    key = discord_api_key()
    if key:
        request.add_header("X-API-Key", key)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8", errors="replace")
            data = json.loads(payload)
            return data if isinstance(data, dict) else None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def fetch_discord_status(*, force: bool = False) -> dict | None:
    global _STATUS_CACHE
    now = time.time()
    if not force and _STATUS_CACHE and now - _STATUS_CACHE[0] < CACHE_TTL:
        return _STATUS_CACHE[1]

    data = _api_request("/api/discord/status")
    _STATUS_CACHE = (now, data)
    return data


def fetch_discord_token(*, force: bool = False) -> str:
    global _TOKEN_CACHE
    now = time.time()
    if not force and _TOKEN_CACHE and now - _TOKEN_CACHE[0] < CACHE_TTL:
        return _TOKEN_CACHE[1]

    data = _api_request("/api/discord/token")
    token = ""
    if data and isinstance(data.get("token"), str):
        token = data["token"].strip()
    _TOKEN_CACHE = (now, token)
    return token


def clear_discord_api_cache() -> None:
    global _STATUS_CACHE, _TOKEN_CACHE
    _STATUS_CACHE = None
    _TOKEN_CACHE = None

"""
API Discord pour VM — heberge le token bot, le client TOOL OAP le recupere.

Lancer sur la VM:
  python discord_api_server.py
  ou: start_discord_api.bat

Config: discord_api.env (copie discord_api.env.example)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_server_config() -> dict[str, str]:
    values: dict[str, str] = {}
    for name in ("discord_api.env", ".env"):
        values.update(_parse_env_file(ROOT / name))
    for key in ("DISCORD_TOKEN", "DISCORD_API_KEY", "DISCORD_API_HOST", "DISCORD_API_PORT"):
        env_value = os.getenv(key, "").strip()
        if env_value:
            values[key] = env_value
    return values


def discord_bot_info(token: str) -> dict | None:
    if not token:
        return None
    request = urllib.request.Request(
        "https://discord.com/api/v10/users/@me",
        headers={
            "Authorization": f"Bot {token}",
            "User-Agent": "TOOL_OAP_DiscordAPI/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data if isinstance(data, dict) else None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


class DiscordApiHandler(BaseHTTPRequestHandler):
    token = ""
    api_key = ""

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        if not self.api_key:
            return False
        provided = self.headers.get("X-API-Key", "").strip()
        return bool(provided) and provided == self.api_key

    def do_GET(self) -> None:
        if self.path == "/api/health":
            self._send_json(200, {"ok": True, "service": "tool-oap-discord-api"})
            return

        if self.path == "/api/discord/status":
            info = discord_bot_info(self.token)
            if info:
                self._send_json(
                    200,
                    {
                        "configured": True,
                        "bot_id": str(info.get("id", "")),
                        "bot_username": str(info.get("username", "")),
                        "source": "vm",
                    },
                )
                return
            self._send_json(
                200,
                {
                    "configured": bool(self.token),
                    "bot_id": "",
                    "bot_username": "",
                    "source": "vm",
                    "valid": False,
                },
            )
            return

        if self.path == "/api/discord/token":
            if not self._authorized():
                self._send_json(401, {"error": "api_key_required"})
                return
            if not self.token:
                self._send_json(503, {"error": "discord_token_missing"})
                return
            self._send_json(200, {"token": self.token, "source": "vm"})
            return

        self._send_json(404, {"error": "not_found"})


def main() -> int:
    config = load_server_config()
    token = config.get("DISCORD_TOKEN", "").strip()
    api_key = config.get("DISCORD_API_KEY", "").strip()
    host = config.get("DISCORD_API_HOST", "0.0.0.0").strip() or "0.0.0.0"
    port = int(config.get("DISCORD_API_PORT", "8780") or "8780")

    if not token:
        print("ERREUR: DISCORD_TOKEN manquant dans discord_api.env")
        return 1
    if not api_key:
        print("ERREUR: DISCORD_API_KEY manquant dans discord_api.env")
        return 1

    DiscordApiHandler.token = token
    DiscordApiHandler.api_key = api_key

    server = ThreadingHTTPServer((host, port), DiscordApiHandler)
    info = discord_bot_info(token)
    bot_label = info.get("username", "?") if info else "token invalide"
    print(f"API Discord TOOL OAP — http://{host}:{port}")
    print(f"Bot: {bot_label}")
    print("Endpoints: /api/health /api/discord/status /api/discord/token")
    print("Ctrl+C pour arreter.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArret.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

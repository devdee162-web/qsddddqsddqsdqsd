"""Connexion bot Discord — local ou via API VM."""

from __future__ import annotations

import getpass
import os
from pathlib import Path

from app_paths import _parse_env_file, _write_env_file, config_path
from discord_api_client import (
    clear_discord_api_cache,
    discord_api_configured,
    fetch_discord_status,
    fetch_discord_token,
    last_api_error,
    resolve_discord_api_url,
)

PLACEHOLDER = "ton_token_bot_ici"


def get_local_discord_token(data_dir: Path) -> str:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if token and token != PLACEHOLDER:
        return token
    cfg = config_path(data_dir)
    if cfg.exists():
        token = _parse_env_file(cfg).get("DISCORD_TOKEN", "").strip()
        if token and token != PLACEHOLDER:
            os.environ["DISCORD_TOKEN"] = token
            return token
    return ""


def get_discord_token(data_dir: Path, *, force_api: bool = False) -> str:
    if discord_api_configured():
        token = fetch_discord_token(force=force_api)
        if token:
            os.environ["DISCORD_TOKEN"] = token
            return token

    token = get_local_discord_token(data_dir)
    if token:
        return token
    return ""


def save_discord_token(data_dir: Path, token: str) -> None:
    cleaned = token.strip()
    cfg = config_path(data_dir)
    values = _parse_env_file(cfg) if cfg.exists() else {}
    values["DISCORD_TOKEN"] = cleaned
    _write_env_file(cfg, values)
    os.environ["DISCORD_TOKEN"] = cleaned
    clear_discord_api_cache()


def mask_token(token: str) -> str:
    if len(token) < 12:
        return "non configure"
    return f"{token[:8]}...{token[-4:]}"


def discord_token_status(data_dir: Path) -> str:
    if discord_api_configured():
        status = fetch_discord_status()
        if status and status.get("configured"):
            source = status.get("source", "")
            name = status.get("bot_username") or ""
            if name:
                suffix = " (partage)" if source == "smb" else ""
                return f"VM connecte ({name}){suffix}"
            if source == "smb":
                return "VM connecte (partage)"
            return "VM connecte"
        api_url = resolve_discord_api_url()
        if api_url:
            detail = last_api_error()
            if detail:
                return f"VM indisponible ({detail})"
            return "VM indisponible"
        return "API VM non configuree"

    token = get_local_discord_token(data_dir)
    if not token:
        return "non configure"
    return f"local ({mask_token(token)})"


def _print_discord_help() -> None:
    print()
    print("=== CONNEXION BOT DISCORD (LOCAL) ===")
    print()
    if discord_api_configured():
        print(f"API VM detectee: {resolve_discord_api_url()}")
        print("Le token peut etre gere sur la VM (discord_api_server.py).")
        print("Cette saisie sert de secours si l'API VM est indisponible.")
        print()
    print("Colle le TOKEN BOT (Developer Portal > ton application > Bot > Reset Token).")
    print()
    print("1. https://discord.com/developers/applications")
    print("2. Ouvre ton application bot")
    print("3. Bot > Reset Token > copie le token")
    print("4. Colle-le ci-dessous (saisie masquee)")
    print()


def prompt_discord_token(data_dir: Path) -> bool:
    _print_discord_help()
    token = getpass.getpass("Token bot Discord (Entree = annuler): ").strip()
    if not token:
        print("Annule.")
        return False
    if token == PLACEHOLDER:
        print("Token invalide.")
        return False
    save_discord_token(data_dir, token)
    print(f"Token local enregistre ({mask_token(token)}).")
    return True


def test_discord_api() -> bool:
    if not discord_api_configured():
        print("API VM non configuree (SYNC_VM_HOST ou DISCORD_API_URL).")
        return False

    print(f"Test API: {resolve_discord_api_url()}")
    status = fetch_discord_status(force=True)
    if not status:
        print("Echec: API VM injoignable.")
        detail = last_api_error()
        if detail:
            print(f"Detail: {detail}")
        print("Sur la VM: lance open_discord_api_firewall.bat en administrateur.")
        print("Puis relance start_discord_api.bat (publie aussi sur le partage SMB).")
        return False

    if status.get("bot_username"):
        print(f"OK: bot Discord '{status['bot_username']}' via VM.")
    elif status.get("configured"):
        print("OK: token present sur la VM (verification bot en attente).")
    else:
        print("Echec: token Discord manquant sur la VM.")
        return False

    token = fetch_discord_token(force=True)
    if not token:
        print("Echec: impossible de recuperer le token (verifie DISCORD_API_KEY).")
        return False

    print("OK: token recupere depuis la VM.")
    return True


def ensure_discord_token(data_dir: Path, *, interactive: bool = True) -> str | None:
    token = get_discord_token(data_dir)
    if token:
        return token
    if not interactive:
        return None

    if discord_api_configured():
        print("API VM configuree mais Discord indisponible.")
        test_discord_api()
        token = get_discord_token(data_dir, force_api=True)
        if token:
            return token

    print("Connexion bot Discord requise pour cette action.")
    if prompt_discord_token(data_dir):
        return get_discord_token(data_dir)
    return None

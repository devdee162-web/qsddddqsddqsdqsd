"""Connexion bot Discord — token saisi localement (AppData), jamais dans le code."""

from __future__ import annotations

import getpass
import os
from pathlib import Path

from app_paths import _parse_env_file, _write_env_file, config_path

PLACEHOLDER = "ton_token_bot_ici"


def get_discord_token(data_dir: Path) -> str:
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


def save_discord_token(data_dir: Path, token: str) -> None:
    cleaned = token.strip()
    cfg = config_path(data_dir)
    values = _parse_env_file(cfg) if cfg.exists() else {}
    values["DISCORD_TOKEN"] = cleaned
    _write_env_file(cfg, values)
    os.environ["DISCORD_TOKEN"] = cleaned


def mask_token(token: str) -> str:
    if len(token) < 12:
        return "non configure"
    return f"{token[:8]}...{token[-4:]}"


def discord_token_status(data_dir: Path) -> str:
    token = get_discord_token(data_dir)
    if not token:
        return "non configure"
    return f"configure ({mask_token(token)})"


def _print_discord_help() -> None:
    print()
    print("=== CONNEXION BOT DISCORD ===")
    print()
    print("Discord n'autorise pas la connexion e-mail/mot de passe pour un bot.")
    print("Colle ici le TOKEN BOT (Developer Portal > ton application > Bot > Reset Token).")
    print()
    print("1. https://discord.com/developers/applications")
    print("2. Ouvre ton application bot")
    print("3. Bot > Reset Token > copie le token")
    print("4. Colle-le ci-dessous (saisie masquee, comme un mot de passe)")
    print()
    print("Le token est enregistre uniquement sur ce PC (AppData), pas sur GitHub.")
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
    print(f"Token enregistre ({mask_token(token)}).")
    return True


def ensure_discord_token(data_dir: Path, *, interactive: bool = True) -> str | None:
    token = get_discord_token(data_dir)
    if token:
        return token
    if not interactive:
        return None
    print("Connexion bot Discord requise pour cette action.")
    if prompt_discord_token(data_dir):
        return get_discord_token(data_dir)
    return None

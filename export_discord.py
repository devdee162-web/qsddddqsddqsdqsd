"""
TOOL OAP - Export Discord et recherche locale dans les dossiers.
"""

from __future__ import annotations

import asyncio
import csv
import getpass
import hashlib
import html
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import discord
from colorama import Fore, Style, init

from auto_setup import prepare_environment, run_startup_automation
from app_paths import get_data_dir, is_frozen
from discord_api_client import discord_api_configured
from discord_auth import (
    discord_token_status,
    ensure_discord_token,
    prompt_discord_token,
    test_discord_api,
)
from updater import auto_check_on_start, resolve_github_repo, run_update_menu
from version import VERSION


def get_app_dir() -> Path:
    return get_data_dir()


INSTALL_DIR, DATA_DIR = prepare_environment()
APP_DIR = DATA_DIR
UPDATE_DIR = INSTALL_DIR if is_frozen() else DATA_DIR
os.chdir(DATA_DIR)

init(autoreset=True)

CATEGORY_ID = int(os.getenv("CATEGORY_ID", "1520602288635252886"))
GUILD_ID = os.getenv("GUILD_ID", "").strip()
GUILD_ID = int(GUILD_ID) if GUILD_ID else None
EXCLUDED_CHANNELS = {
    int(x.strip())
    for x in os.getenv(
        "EXCLUDED_CHANNELS",
        "1521941017312362526,1521899575101882499",
    ).split(",")
    if x.strip()
}
OUTPUT_DIR = DATA_DIR / os.getenv("OUTPUT_DIR", "export_discord")
DOSSIERS_DIR = DATA_DIR / os.getenv("DOSSIERS_DIR", "dossiers")
ACCOUNTS_FILE = DATA_DIR / os.getenv("ACCOUNTS_FILE", "accounts.json")
DOSSIER_PREFIX = os.getenv("DOSSIER_PREFIX", "📂")
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "8765"))
SYNC_VM_ENABLED = os.getenv("SYNC_VM_ENABLED", "false").strip().lower() in {
    "1",
    "true",
    "oui",
    "yes",
}
SYNC_VM_HOST = os.getenv("SYNC_VM_HOST", "192.168.1.100").strip()
SYNC_VM_USER = os.getenv("SYNC_VM_USER", "Discord").strip()
SYNC_VM_PASS = os.getenv("SYNC_VM_PASS", "#$6z8B@p35gZKa").strip()
SYNC_VM_SHARE = os.getenv("SYNC_VM_SHARE", "tool_oap").strip()
SYNC_VM_UNC = os.getenv("SYNC_VM_UNC", "").strip()
GITHUB_REPO = resolve_github_repo(os.getenv("GITHUB_REPO", "devdee162-web/qsddddqsddqsdqsd"), DATA_DIR)
AUTO_UPDATE_ON_START = os.getenv("AUTO_UPDATE_ON_START", "true").strip().lower() in {
    "1",
    "true",
    "oui",
    "yes",
}
AUTO_MODE = os.getenv("AUTO_MODE", "true").strip().lower() in {
    "1",
    "true",
    "oui",
    "yes",
}
AUTO_SYNC_ON_START = os.getenv("AUTO_SYNC_ON_START", "false").strip().lower() in {
    "1",
    "true",
    "oui",
    "yes",
}
UPDATE_CHECK_HOURS = max(1, int(os.getenv("UPDATE_CHECK_HOURS", "24") or "24"))
SYNC_CACHE_FILE = DATA_DIR / ".tool_oap_sync.json"
BOT_PERMISSIONS = 68624  # voir salons + lire historique + envoyer + gerer salons

_vm_share_connected = False

EXPORTABLE = (discord.TextChannel, discord.ForumChannel)

BANNER_SPLIT_AT = 63

BANNER_LINES = [
    " _____                          __                            ______          __        ____           __            ",
    "/\\  __`\\                       /\\ \\__  __                    /\\  _  \\        /\\ \\__  __/\\  _`\\        /\\ \\           ",
    "\\ \\ \\/\\ \\  _____   _ __    __  \\ \\ ,_\\/\\_\\    ___     ___    \\ \\ \\L\\ \\    ___\\ \\ ,_\\/\\_\\ \\ \\L\\ \\ __   \\_\\ \\    ___   ",
    " \\ \\ \\ \\ \\/\\ '__`\\/\\`'__\\/'__`\\ \\ \\ \\/\\/\\ \\  / __`\\ /' _ `\\   \\ \\  __ \\ /' _ `\\ \\ \\/\\/\\ \\ \\ ,__/'__`\\ /'_` \\  / __`\\ ",
    "  \\ \\ \\_\\ \\ \\ \\L\\ \\ \\ \\//\\ \\L\\.\\_\\ \\ \\_\\ \\ \\/\\ \\L\\ \\/\\ \\/\\ \\   \\ \\ \\/\\ \\/\\ \\/\\ \\ \\ \\_\\ \\ \\ \\ \\/\\  __//\\ \\L\\ \\/\\ \\L\\ \\",
    "   \\ \\_____\\ \\ ,__/\\ \\_\\\\ \\__/.\\_\\\\ \\__\\\\ \\_\\ \\____/\\ \\_\\ \\_\\   \\ \\_\\ \\_\\ \\_\\ \\_\\ \\__\\\\ \\_\\ \\_\\ \\____\\ \\___,_\\ \\____/",
    "    \\/_____/\\ \\ \\/  \\/_/ \\/__/\\/_/ \\/__/ \\/_/\\/___/  \\/_/\\/_/    \\/_/\\/_/\\/_/\\/_/\\/__/ \\/_/\\/_/\\/____/\\/__,_ /\\/___/ ",
    "             \\ \\_\\                                                                                                   ",
    "              \\/_/",
]


def banner_text() -> str:
    return "\n".join(BANNER_LINES)


def banner_for_discord() -> str:
    safe = banner_text().replace("`", "'")
    return f"```\n{safe}\n```"


def dossier_filename(prenom: str, nom: str) -> str:
    prenom_fmt = prenom.strip().title()
    nom_fmt = nom.strip().title()
    if nom_fmt:
        return f"{prenom_fmt} {nom_fmt}.txt"
    return f"{prenom_fmt}.txt"


def dossier_title(prenom: str, nom: str) -> str:
    if nom.strip():
        return f"# {(f'{prenom}-{nom}').upper()}"
    return f"# {prenom.upper()}"


def print_banner() -> None:
    for line in BANNER_LINES:
        if len(line) <= BANNER_SPLIT_AT:
            print(f"{Fore.YELLOW}{line}{Style.RESET_ALL}")
        else:
            print(
                f"{Fore.YELLOW}{line[:BANNER_SPLIT_AT]}"
                f"{Fore.BLUE}{line[BANNER_SPLIT_AT:]}{Style.RESET_ALL}"
            )
    print()


def clear_line() -> None:
    sys.stdout.write("\r" + " " * 80 + "\r")
    sys.stdout.flush()


def spinner_loop(stop_event: threading.Event, message: str) -> None:
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    index = 0
    while not stop_event.is_set():
        frame = frames[index % len(frames)]
        sys.stdout.write(f"\r{Fore.CYAN}{message} {frame}{Style.RESET_ALL}")
        sys.stdout.flush()
        index += 1
        time.sleep(0.08)
    clear_line()


def run_with_spinner(message: str, seconds: float = 1.2) -> None:
    stop_event = threading.Event()
    thread = threading.Thread(target=spinner_loop, args=(stop_event, message), daemon=True)
    thread.start()
    time.sleep(seconds)
    stop_event.set()
    thread.join()


def animate_loading_bar(label: str = "Chargement", width: int = 36) -> None:
    for step in range(width + 1):
        filled = "█" * step + "░" * (width - step)
        percent = int((step / width) * 100)
        sys.stdout.write(
            f"\r{Fore.CYAN}{label} [{filled}] {percent}%{Style.RESET_ALL}"
        )
        sys.stdout.flush()
        time.sleep(0.025)
    print()


def clear_screen() -> None:
    if os.name == "nt":
        os.system("cls")
    else:
        sys.stdout.write("\033[H\033[J")
        sys.stdout.flush()


def animate_banner() -> None:
    colors = [Fore.YELLOW, Fore.BLUE, Fore.CYAN, Fore.MAGENTA]

    for frame in range(6):
        clear_screen()
        wave = frame % len(colors)
        print()
        for index, line in enumerate(BANNER_LINES):
            if len(line) <= BANNER_SPLIT_AT:
                color = colors[(index + wave) % len(colors)]
                print(f"{color}{line}{Style.RESET_ALL}")
            else:
                print(
                    f"{Fore.YELLOW}{line[:BANNER_SPLIT_AT]}"
                    f"{Fore.BLUE}{line[BANNER_SPLIT_AT:]}{Style.RESET_ALL}"
                )
        time.sleep(0.1)

    clear_screen()
    print()
    print_banner()
    animate_loading_bar("TOOL OAP")


def animate_success(message: str) -> None:
    for color in (Fore.GREEN, Fore.CYAN, Fore.GREEN):
        clear_line()
        sys.stdout.write(f"\r{color}✓ {message}{Style.RESET_ALL}\n")
        sys.stdout.flush()
        time.sleep(0.12)


def animate_pulse_text(message: str, cycles: int = 3) -> None:
    colors = (Fore.CYAN, Fore.BLUE, Fore.MAGENTA, Fore.CYAN)
    for i in range(cycles):
        color = colors[i % len(colors)]
        clear_line()
        sys.stdout.write(f"\r{color}>> {message}{Style.RESET_ALL}")
        sys.stdout.flush()
        time.sleep(0.2)
    print()


def animate_typing(text: str, delay: float = 0.02) -> None:
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def animate_error(message: str) -> None:
    for color in (Fore.RED, Fore.YELLOW, Fore.RED):
        clear_line()
        sys.stdout.write(f"\r{color}✗ {message}{Style.RESET_ALL}\n")
        sys.stdout.flush()
        time.sleep(0.1)


def animate_warning(message: str) -> None:
    for color in (Fore.YELLOW, Fore.RED, Fore.YELLOW):
        clear_line()
        sys.stdout.write(f"\r{color}! {message}{Style.RESET_ALL}\n")
        sys.stdout.flush()
        time.sleep(0.1)


def animate_info(message: str) -> None:
    animate_pulse_text(message, cycles=2)


def animate_transition(message: str = "Chargement", duration: float = 0.45) -> None:
    run_with_spinner(message, duration)


def animate_section_title(title: str) -> None:
    print()
    sys.stdout.write(Fore.CYAN)
    for char in title:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(0.008)
    print(Style.RESET_ALL)


def animate_progress(current: int, total: int, label: str) -> None:
    if total <= 0:
        return
    width = 28
    filled = int(width * current / total)
    bar = "█" * filled + "░" * (width - filled)
    percent = int((current / total) * 100)
    sys.stdout.write(
        f"\r{Fore.CYAN}{label} [{bar}] {percent}% ({current}/{total}){Style.RESET_ALL}"
    )
    sys.stdout.flush()
    if current >= total:
        print()


def animate_menu_open(title: str) -> None:
    animate_transition("Ouverture du menu", 0.35)
    animate_section_title(title)


def animate_result_box(title: str, lines: list[str]) -> None:
    animate_loading_bar(title, width=24)
    print(f"\n{Fore.GREEN}{'=' * 50}{Style.RESET_ALL}")
    for line in lines:
        print(f"{Fore.GREEN}{line}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'=' * 50}{Style.RESET_ALL}")


def animate_invalid_choice() -> None:
    animate_error("Choix invalide.")


@dataclass
class User:
    username: str
    role: str


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()


def load_accounts() -> dict:
    if not ACCOUNTS_FILE.exists():
        return {"users": {}}
    with ACCOUNTS_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def save_accounts(data: dict) -> None:
    with ACCOUNTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def valid_username(username: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_]{3,20}", username))


def ask_password(prompt: str = "Mot de passe: ") -> str:
    return getpass.getpass(prompt)


def create_account(username: str, password: str, role: str = "user") -> bool:
    if not valid_username(username):
        animate_error("Pseudo invalide (3-20 caracteres, lettres/chiffres/_).")
        return False
    if len(password) < 4:
        animate_error("Mot de passe trop court (min 4 caracteres).")
        return False

    data = load_accounts()
    if username in data["users"]:
        animate_error("Ce pseudo existe deja.")
        return False

    salt = secrets.token_hex(16)
    data["users"][username] = {
        "password_hash": hash_password(password, salt),
        "salt": salt,
        "role": role,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save_accounts(data)
    animate_success(f"Compte '{username}' cree.")
    return True


def authenticate(username: str, password: str) -> User | None:
    data = load_accounts()
    account = data["users"].get(username)
    if not account:
        return None
    if hash_password(password, account["salt"]) != account["password_hash"]:
        return None
    return User(username=username, role=account.get("role", "user"))


def setup_first_account() -> User | None:
    animate_menu_open("=== PREMIER LANCEMENT ===")
    animate_info("Creation du compte administrateur.")
    username = input("Pseudo admin: ").strip()
    password = ask_password("Mot de passe: ")
    confirm = ask_password("Confirmer: ")
    if password != confirm:
        animate_error("Les mots de passe ne correspondent pas.")
        return None
    if not create_account(username, password, role="admin"):
        return None
    return User(username=username, role="admin")


def login_screen() -> User | None:
    data = load_accounts()
    if not data["users"]:
        return setup_first_account()

    animate_menu_open("=== CONNEXION ===")
    for attempt in range(3):
        username = input("Pseudo: ").strip()
        if not username:
            return None
        animate_transition("Verification", 0.35)
        password = ask_password()
        user = authenticate(username, password)
        if user:
            animate_success(f"Connecte: {user.username} ({user.role})")
            return user
        animate_error(f"Identifiants incorrects ({2 - attempt} essai(s) restant(s)).")

    animate_error("Trop de tentatives.")
    return None


def change_password(user: User) -> None:
    current = ask_password("Mot de passe actuel: ")
    if not authenticate(user.username, current):
        animate_error("Mot de passe actuel incorrect.")
        return

    new_pass = ask_password("Nouveau mot de passe: ")
    confirm = ask_password("Confirmer: ")
    if new_pass != confirm:
        animate_error("Les mots de passe ne correspondent pas.")
        return
    if len(new_pass) < 4:
        animate_error("Mot de passe trop court.")
        return

    data = load_accounts()
    salt = secrets.token_hex(16)
    data["users"][user.username]["salt"] = salt
    data["users"][user.username]["password_hash"] = hash_password(new_pass, salt)
    save_accounts(data)
    animate_success("Mot de passe modifie.")


def admin_create_user() -> None:
    username = input("Nouveau pseudo: ").strip()
    password = ask_password("Mot de passe: ")
    confirm = ask_password("Confirmer: ")
    if password != confirm:
        animate_error("Les mots de passe ne correspondent pas.")
        return
    create_account(username, password, role="user")


def admin_delete_user(current: User) -> None:
    username = input("Pseudo a supprimer: ").strip()
    if username == current.username:
        animate_error("Tu ne peux pas supprimer ton propre compte.")
        return
    data = load_accounts()
    if username not in data["users"]:
        animate_error("Compte introuvable.")
        return
    del data["users"][username]
    save_accounts(data)
    animate_success(f"Compte '{username}' supprime.")


def list_users() -> None:
    data = load_accounts()
    animate_transition("Chargement des comptes", 0.35)
    animate_section_title("=== COMPTES ===")
    for name, info in sorted(data["users"].items()):
        print(f"  - {name} ({info.get('role', 'user')})")


def menu_compte(user: User) -> None:
    while True:
        animate_menu_open(f"=== MON COMPTE ({user.username}) ===")
        print(f"  Bot Discord: {discord_token_status(DATA_DIR)}")
        print("  1. Changer mon mot de passe")
        print("  2. Connexion bot Discord (token local / secours)")
        print("  3. Tester API Discord VM")
        if user.role == "admin":
            print("  4. Creer un compte")
            print("  5. Supprimer un compte")
            print("  6. Lister les comptes")
        print("  0. Retour")

        choice = input("\nChoix: ").strip()

        if choice == "1":
            change_password(user)
        elif choice == "2":
            if prompt_discord_token(DATA_DIR):
                animate_success("Token bot Discord local enregistre.")
            else:
                animate_info("Connexion bot Discord annulee.")
        elif choice == "3":
            if test_discord_api():
                animate_success("API Discord VM operationnelle.")
            else:
                animate_error("API Discord VM indisponible.")
        elif choice == "4" and user.role == "admin":
            admin_create_user()
        elif choice == "5" and user.role == "admin":
            admin_delete_user(user)
        elif choice == "6" and user.role == "admin":
            list_users()
        elif choice == "0":
            break
        else:
            animate_invalid_choice()


def bot_invite_url(client_id: int) -> str:
    return (
        "https://discord.com/api/oauth2/authorize"
        f"?client_id={client_id}&permissions={BOT_PERMISSIONS}&scope=bot"
    )


def category_error_message(client_id: int) -> str:
    invite = bot_invite_url(client_id)
    return (
        f"ERREUR: Categorie introuvable ({CATEGORY_ID}).\n\n"
        "Verifie que:\n"
        "- Le bot est bien sur le serveur\n"
        "- L'ID correspond bien a une categorie Discord\n"
        "- Le bot peut gerer les salons (permission Manage Channels)\n\n"
        f"Ajoute/mets a jour le bot:\n   {invite}\n\n"
        "Optionnel: mets GUILD_ID dans .env pour cibler un serveur precis."
    )


async def get_guild_category(
    client: discord.Client,
) -> tuple[discord.Guild | None, discord.CategoryChannel | None, str | None]:
    guild, category = find_category(client, CATEGORY_ID)
    if category is not None and guild is not None:
        return guild, category, None

    app = await client.application_info()
    return None, None, category_error_message(app.id)


def build_channel_name(prenom: str, nom: str) -> str:
    base = f"{prenom}-{nom}".lower() if nom.strip() else prenom.lower()
    base = re.sub(r"[^a-z0-9\-_]", "-", base)
    base = re.sub(r"-+", "-", base).strip("-") or "dossier"
    name = f"{DOSSIER_PREFIX}{base}"
    return name[:100]


def unique_channel_name(category: discord.CategoryChannel, base_name: str) -> str:
    existing = {ch.name for ch in category.channels}
    if base_name not in existing:
        return base_name
    counter = 2
    while f"{base_name}-{counter}" in existing:
        counter += 1
    return f"{base_name}-{counter}"[:100]


def append_local_dossier(dossier_dir: Path, dossier_data: dict) -> None:
    with (dossier_dir / "dossier.json").open("w", encoding="utf-8") as f:
        json.dump(dossier_data, f, ensure_ascii=False, indent=2)

    bloc = dossier_data.get("bloc_note", "")
    filename = dossier_data.get("fichier", "bloc_note.txt")
    (dossier_dir / filename).write_text(bloc, encoding="utf-8")


def collect_dossier_identity() -> tuple[str, str] | None:
    animate_menu_open("=== CREER UN DOSSIER ===")
    prenom = safe_input("Prenom / pseudo: ")
    if prenom is None:
        return None
    nom = safe_input("Nom (Entree si aucun): ")
    if nom is None:
        return None
    if not prenom:
        animate_error("Prenom ou pseudo obligatoire.")
        return None
    return prenom, nom


def safe_input(prompt: str) -> str | None:
    try:
        return input(prompt).strip()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{Fore.YELLOW}Saisie annulee.{Style.RESET_ALL}")
        return None


def collect_bloc_note(dossier_dir: Path, prenom: str, nom: str) -> str | None:
    filename = dossier_filename(prenom, nom)
    note_path = dossier_dir / filename
    note_path.write_text(f"{dossier_title(prenom, nom)}\n\n", encoding="utf-8")

    animate_menu_open("=== BLOC-NOTE LIBRE ===")
    animate_info("Ecris ce que tu veux, sans champs imposes.")

    if sys.platform == "win32":
        os.startfile(note_path)
        animate_warning("Le bloc-note Windows s'est ouvert.")
        print("1. Ecris tes infos librement")
        print("2. Enregistre (Ctrl+S) dans le bloc-note")
        print("3. Ferme le bloc-note")
        confirm = safe_input("\nAppuie sur Entree quand c'est fait (ou 'annuler'): ")
        if confirm is None or confirm.lower() in {"annuler", "cancel", "q"}:
            return None
    else:
        print("Termine par une ligne contenant uniquement 'fin'.\n")
        lines: list[str] = []
        while True:
            try:
                line = input()
            except (KeyboardInterrupt, EOFError):
                print(f"\n{Fore.YELLOW}Saisie annulee.{Style.RESET_ALL}")
                return None
            if line.strip().lower() == "fin":
                break
            lines.append(line)
        note_path.write_text("\n".join(lines), encoding="utf-8")

    return note_path.read_text(encoding="utf-8").strip()


async def send_dossier_once(
    channel: discord.TextChannel,
    prenom: str,
    nom: str,
    bloc_note: str,
    dossier_dir: Path,
) -> discord.Message:
    filename = dossier_filename(prenom, nom)
    file_path = dossier_dir / filename
    content = bloc_note.strip() or dossier_title(prenom, nom)
    file_path.write_text(content, encoding="utf-8")

    run_with_spinner("Envoi sur Discord", 0.7)
    return await channel.send(
        banner_for_discord(),
        file=discord.File(file_path, filename=filename),
    )


async def creer_dossier_action(
    client: discord.Client,
    user: User,
    prenom: str,
    nom: str,
    bloc_note: str,
    dossier_dir: Path,
    attachment_path: str = "",
) -> None:
    guild, category, error = await get_guild_category(client)
    if error:
        print(error)
        return

    channel_name = unique_channel_name(category, build_channel_name(prenom, nom))
    filename = dossier_filename(prenom, nom)

    animate_info(f"Creation du salon Discord #{channel_name}")
    run_with_spinner("Creation du salon en cours", 1.0)
    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        reason=f"Dossier OAP cree par {user.username}",
    )

    dossier_data = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.username,
        "prenom": prenom,
        "nom": nom,
        "bloc_note": bloc_note,
        "fichier": filename,
        "guild_id": str(guild.id),
        "guild_name": guild.name,
        "category_id": str(category.id),
        "category_name": category.name,
        "channel_id": str(channel.id),
        "channel_name": channel.name,
        "attachments": [],
        "messages": [],
    }

    msg = await send_dossier_once(channel, prenom, nom, bloc_note, dossier_dir)
    dossier_data["messages"].append(str(msg.id))
    append_local_dossier(dossier_dir, dossier_data)
    animate_success(f"Banner + {filename} envoye sur Discord.")

    if attachment_path:
        local_file = Path(attachment_path)
        if local_file.exists() and local_file.is_file():
            file_msg = await channel.send(file=discord.File(local_file))
            dest = dossier_dir / "pieces_jointes"
            dest.mkdir(exist_ok=True)
            dest_file = dest / local_file.name
            dest_file.write_bytes(local_file.read_bytes())
            dossier_data["attachments"].append(dest_file.name)
            dossier_data["messages"].append(str(file_msg.id))
            append_local_dossier(dossier_dir, dossier_data)
            animate_success("Fichier joint envoye.")
        else:
            animate_error("Fichier joint introuvable.")

    animate_result_box(
        "DOSSIER CREE",
        [
            f"Salon Discord: #{channel.name}",
            f"Fichier: {(dossier_dir / filename).resolve()}",
            f"Dossier local: {dossier_dir.resolve()}",
        ],
    )
    sync_path_to_vm(dossier_dir)


async def run_discord_task(task, user: User | None = None, *, _retry: bool = False) -> None:
    token = ensure_discord_token(DATA_DIR)
    if not token:
        if discord_api_configured():
            animate_error("Discord via VM indisponible. Menu 5 > Tester API Discord VM.")
        else:
            animate_error("Token bot Discord manquant. Menu 5 > Connexion bot Discord.")
        return

    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True

    client = discord.Client(intents=intents)
    error_message: str | None = None

    @client.event
    async def on_ready() -> None:
        nonlocal error_message
        animate_success(f"Connecte: {client.user}")
        try:
            if user is not None:
                await task(client, user)
            else:
                await task(client)
        except discord.Forbidden:
            app = await client.application_info()
            error_message = (
                "ERREUR: Permissions insuffisantes.\n"
                f"Reinvite le bot avec ce lien:\n   {bot_invite_url(app.id)}"
            )
        except Exception as exc:
            error_message = f"ERREUR: {exc}"
        finally:
            await client.close()

    stop_spinner = threading.Event()
    spinner = threading.Thread(
        target=spinner_loop,
        args=(stop_spinner, "Connexion au bot Discord"),
        daemon=True,
    )
    spinner.start()
    try:
        await client.start(token)
    except discord.LoginFailure:
        stop_spinner.set()
        spinner.join()
        animate_error("Token Discord invalide ou revoque.")
        if discord_api_configured():
            animate_info("Verifie le token sur la VM (discord_api.env).")
        elif not _retry and prompt_discord_token(DATA_DIR):
            await run_discord_task(task, user, _retry=True)
        return
    finally:
        stop_spinner.set()
        spinner.join()

    if error_message:
        animate_error(error_message.split("\n")[0])
        print(error_message)


def menu_creer_dossier(user: User) -> None:
    identity = collect_dossier_identity()
    if not identity:
        return
    prenom, nom = identity

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dossier_dir = DOSSIERS_DIR / f"{timestamp}_{safe_filename(build_channel_name(prenom, nom))}"
    dossier_dir.mkdir(parents=True, exist_ok=True)

    bloc_note = collect_bloc_note(dossier_dir, prenom, nom)
    if bloc_note is None:
        return

    file_path = safe_input("\nFichier a joindre (Entree = aucun): ")
    if file_path is None:
        return
    attachment = file_path.strip().strip('"')

    async def task(client: discord.Client) -> None:
        await creer_dossier_action(
            client, user, prenom, nom, bloc_note, dossier_dir, attachment
        )

    asyncio.run(run_discord_task(task))


def find_local_dossiers() -> list[Path]:
    if not DOSSIERS_DIR.exists():
        return []
    dossiers = [
        folder
        for folder in DOSSIERS_DIR.iterdir()
        if folder.is_dir() and (folder / "dossier.json").exists()
    ]
    return sorted(dossiers, key=lambda p: p.stat().st_mtime, reverse=True)


def load_dossier_meta(dossier_dir: Path) -> dict:
    with (dossier_dir / "dossier.json").open(encoding="utf-8") as f:
        return json.load(f)


def get_dossier_text_path(dossier_dir: Path, data: dict) -> Path:
    fichier = data.get("fichier")
    if fichier:
        path = dossier_dir / fichier
        if path.exists():
            return path

    for name in ("bloc_note.txt", "infos.txt"):
        path = dossier_dir / name
        if path.exists():
            return path

    txts = sorted(dossier_dir.glob("*.txt"))
    if txts:
        return txts[0]

    filename = dossier_filename(data.get("prenom", ""), data.get("nom", ""))
    return dossier_dir / filename


def read_dossier_content(dossier_dir: Path, data: dict | None = None) -> str:
    meta = data or load_dossier_meta(dossier_dir)
    path = get_dossier_text_path(dossier_dir, meta)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return meta.get("bloc_note", "")


def save_dossier_content(dossier_dir: Path, content: str) -> dict:
    data = load_dossier_meta(dossier_dir)
    data["bloc_note"] = content
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    if not data.get("fichier"):
        data["fichier"] = get_dossier_text_path(dossier_dir, data).name
    append_local_dossier(dossier_dir, data)
    sync_path_to_vm(dossier_dir, quiet=True)
    return data


def dossier_label(data: dict) -> str:
    prenom = data.get("prenom", "?")
    nom = data.get("nom", "")
    name = f"{prenom} {nom}".strip()
    channel = data.get("channel_name", "?")
    return f"{name} | #{channel}"


def choose_local_dossier() -> Path | None:
    dossiers = find_local_dossiers()
    if not dossiers:
        animate_error(f"Aucun dossier cree dans {DOSSIERS_DIR.resolve()}")
        return None

    animate_section_title("=== DOSSIERS CREES ===")
    for index, dossier_dir in enumerate(dossiers, 1):
        data = load_dossier_meta(dossier_dir)
        date = data.get("created_at", "?")[:10]
        print(f"  {index}. {dossier_label(data)} | {date}")

    choice = safe_input("\nNumero (Entree = annuler): ")
    if not choice or choice is None:
        return None
    if not choice.isdigit() or not (1 <= int(choice) <= len(dossiers)):
        animate_error("Choix invalide.")
        return None
    return dossiers[int(choice) - 1]


def list_local_dossiers_created() -> None:
    dossiers = find_local_dossiers()
    if not dossiers:
        animate_error("Aucun dossier cree.")
        return

    animate_transition("Chargement des dossiers", 0.4)
    animate_section_title(f"=== LISTE DES DOSSIERS ({len(dossiers)}) ===")
    for dossier_dir in dossiers:
        data = load_dossier_meta(dossier_dir)
        print(f"{Fore.YELLOW}{dossier_label(data)}{Style.RESET_ALL}")
        print(f"  Cree le   : {data.get('created_at', '?')[:19]}")
        print(f"  Cree par  : {data.get('created_by', '?')}")
        print(f"  Salon ID  : {data.get('channel_id', '?')}")
        print(f"  Fichier   : {get_dossier_text_path(dossier_dir, data).name}")
        print(f"  Dossier   : {dossier_dir.name}")
        if data.get("updated_at"):
            print(f"  Modifie   : {data.get('updated_at', '')[:19]}")
        print()


def show_local_dossier(dossier_dir: Path) -> None:
    data = load_dossier_meta(dossier_dir)
    content = read_dossier_content(dossier_dir, data)
    animate_transition("Lecture du dossier", 0.35)
    animate_section_title(f"=== {dossier_label(data)} ===")
    print(content or "(vide)")
    animate_info(f"Fichier: {get_dossier_text_path(dossier_dir, data)}")


def edit_local_dossier(dossier_dir: Path) -> bool:
    data = load_dossier_meta(dossier_dir)
    note_path = get_dossier_text_path(dossier_dir, data)

    animate_info(f"Modification: {dossier_label(data)}")

    if sys.platform == "win32":
        os.startfile(note_path)
        print("Modifie le fichier, enregistre (Ctrl+S), ferme le bloc-note.")
        confirm = safe_input("Appuie sur Entree quand c'est fait (ou 'annuler'): ")
        if confirm is None or confirm.lower() in {"annuler", "cancel", "q"}:
            return False
    else:
        print(f"Ouvre ce fichier: {note_path}")
        confirm = safe_input("Appuie sur Entree apres modification (ou 'annuler'): ")
        if confirm is None or confirm.lower() in {"annuler", "cancel", "q"}:
            return False

    content = note_path.read_text(encoding="utf-8").strip()
    save_dossier_content(dossier_dir, content)
    animate_success("Dossier local mis a jour.")
    return True


async def sync_dossier_discord(client: discord.Client, dossier_dir: Path) -> None:
    data = load_dossier_meta(dossier_dir)
    channel_id = data.get("channel_id")
    if not channel_id:
        animate_error("Ce dossier n'a pas de salon Discord lie.")
        return

    channel = client.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await client.fetch_channel(int(channel_id))
        except discord.HTTPException:
            animate_error(f"Salon Discord introuvable ({channel_id}).")
            return

    if not isinstance(channel, discord.TextChannel):
        animate_error("Le salon lie n'est pas un salon texte.")
        return

    content = read_dossier_content(dossier_dir, data)
    prenom = data.get("prenom", "")
    nom = data.get("nom", "")

    run_with_spinner("Mise a jour Discord", 0.8)

    for msg_id in data.get("messages", []):
        try:
            old_msg = await channel.fetch_message(int(msg_id))
            await old_msg.delete()
        except discord.HTTPException:
            pass

    msg = await send_dossier_once(channel, prenom, nom, content, dossier_dir)
    data["messages"] = [str(msg.id)]
    data["synced_at"] = datetime.now(timezone.utc).isoformat()
    data["bloc_note"] = content
    append_local_dossier(dossier_dir, data)
    animate_success(f"Discord mis a jour: #{channel.name}")


def menu_gerer_dossiers(user: User) -> None:
    while True:
        animate_menu_open("=== GERER LES DOSSIERS CREES ===")
        print("  1. Lister les dossiers")
        print("  2. Voir un dossier")
        print("  3. Modifier un dossier")
        print("  4. Mettre a jour sur Discord")
        print("  0. Retour")

        choice = safe_input("\nChoix: ")
        if choice is None:
            break

        if choice == "1":
            list_local_dossiers_created()
        elif choice == "2":
            dossier_dir = choose_local_dossier()
            if dossier_dir:
                show_local_dossier(dossier_dir)
        elif choice == "3":
            dossier_dir = choose_local_dossier()
            if dossier_dir and edit_local_dossier(dossier_dir):
                sync = safe_input("Mettre a jour Discord aussi ? (o/n): ")
                if sync and sync.lower() in {"o", "oui", "y"}:

                    async def task(client: discord.Client) -> None:
                        await sync_dossier_discord(client, dossier_dir)

                    asyncio.run(run_discord_task(task))
        elif choice == "4":
            dossier_dir = choose_local_dossier()
            if dossier_dir:

                async def task(client: discord.Client) -> None:
                    await sync_dossier_discord(client, dossier_dir)

                asyncio.run(run_discord_task(task))
        elif choice == "0":
            break
        else:
            animate_invalid_choice()
    export_dir: Path
    channel_name: str
    channel_id: str
    message_id: str
    author_name: str
    author_id: str
    created_at: str
    content: str
    attachments: list[str]
    local_files: list[str]
    source: str


def find_exports(base_dir: Path) -> list[Path]:
    if not base_dir.exists():
        return []
    exports = []
    for folder in base_dir.iterdir():
        if folder.is_dir() and (folder / "export_complet.json").exists():
            exports.append(folder)
    return sorted(exports, key=lambda p: p.stat().st_mtime, reverse=True)


def load_export(export_dir: Path) -> dict:
    with (export_dir / "export_complet.json").open(encoding="utf-8") as f:
        return json.load(f)


def highlight(text: str, query: str, max_len: int = 200) -> str:
    if not text:
        return ""
    lower_text = text.lower()
    lower_query = query.lower()
    idx = lower_text.find(lower_query)
    if idx == -1:
        snippet = text[:max_len]
        if len(text) > max_len:
            snippet += "..."
        return snippet

    start = max(0, idx - 60)
    end = min(len(text), idx + len(query) + 80)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet += "..."

    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return pattern.sub(lambda m: f"{Fore.YELLOW}{m.group()}{Style.RESET_ALL}", snippet)


def message_matches(
    query: str,
    author_name: str,
    content: str,
    attachment_names: list[str],
    extra_text: str = "",
) -> bool:
    q = query.lower()
    haystack = " ".join(
        [
            author_name.lower(),
            content.lower(),
            " ".join(attachment_names).lower(),
            extra_text.lower(),
        ]
    )
    return q in haystack


def channel_matches(query: str, channel_name: str) -> bool:
    return query.lower() in channel_name.lower()


def read_attachment_text(export_dir: Path, local_path: str) -> str:
    file_path = export_dir / local_path.replace("\\", "/")
    if not file_path.exists() or file_path.suffix.lower() not in {
        ".txt", ".log", ".md", ".json", ".csv",
    }:
        return ""
    try:
        return file_path.read_text(encoding="utf-8", errors="ignore")[:50000]
    except OSError:
        return ""


def search_export(
    export_dir: Path,
    query: str,
    dossier_filter: str = "",
    author_filter: str = "",
) -> list[SearchHit]:
    data = load_export(export_dir)
    hits: list[SearchHit] = []

    for cat in data.get("categories", []):
        for ch in cat.get("channels", []):
            channel_name = ch.get("channel_name") or ""
            channel_id = ch.get("channel_id") or ""

            if dossier_filter and dossier_filter.lower() not in channel_name.lower():
                continue

            if channel_matches(query, channel_name):
                hits.append(
                    SearchHit(
                        export_dir=export_dir,
                        channel_name=channel_name,
                        channel_id=channel_id,
                        message_id="",
                        author_name="",
                        author_id="",
                        created_at="",
                        content=f"Dossier trouve ({ch.get('message_count', 0)} messages)",
                        attachments=[],
                        local_files=[],
                        source="dossier",
                    )
                )

            for msg in ch.get("messages", []):
                author_name = msg.get("author_name") or ""
                if author_filter and author_filter.lower() not in author_name.lower():
                    continue

                content = msg.get("content") or ""
                attachments = [a.get("filename", "") for a in msg.get("attachments", [])]
                local_files = msg.get("local_attachments") or []

                extra_text = ""
                for local_file in local_files:
                    extra_text += " " + read_attachment_text(export_dir, local_file)

                if not message_matches(query, author_name, content, attachments, extra_text):
                    continue

                source = "message"
                if any(query.lower() in name.lower() for name in attachments):
                    source = "fichier"
                elif extra_text and query.lower() in extra_text.lower():
                    source = "piece_jointe"

                hits.append(
                    SearchHit(
                        export_dir=export_dir,
                        channel_name=channel_name,
                        channel_id=channel_id,
                        message_id=msg.get("id", ""),
                        author_name=author_name,
                        author_id=msg.get("author_id", ""),
                        created_at=msg.get("created_at", ""),
                        content=content,
                        attachments=attachments,
                        local_files=local_files,
                        source=source,
                    )
                )

    return hits


def search_all(
    export_dirs: list[Path],
    query: str,
    dossier_filter: str = "",
    author_filter: str = "",
) -> list[SearchHit]:
    all_hits: list[SearchHit] = []
    for export_dir in export_dirs:
        all_hits.extend(search_export(export_dir, query, dossier_filter, author_filter))
    return all_hits


def print_hit(index: int, hit: SearchHit, query: str) -> None:
    source_colors = {
        "dossier": Fore.BLUE,
        "message": Fore.GREEN,
        "fichier": Fore.MAGENTA,
        "piece_jointe": Fore.CYAN,
    }
    color = source_colors.get(hit.source, Fore.WHITE)

    print(f"\n{color}[{index}] {hit.source.upper()}{Style.RESET_ALL}")
    print(f"  Export  : {hit.export_dir.name}")
    print(f"  Dossier : {Fore.BLUE}#{hit.channel_name}{Style.RESET_ALL} ({hit.channel_id})")
    if hit.author_name:
        print(f"  Auteur  : {hit.author_name} | {hit.created_at[:10]}")
    if hit.content:
        print(f"  Message : {highlight(hit.content, query)}")
    if hit.attachments:
        print(f"  Fichiers: {', '.join(hit.attachments)}")
    if hit.local_files:
        print(f"  Local   : {', '.join(hit.local_files)}")


def list_dossiers(export_dirs: list[Path]) -> None:
    print(f"\n{Fore.CYAN}=== Dossiers disponibles ==={Style.RESET_ALL}\n")
    for export_dir in export_dirs:
        data = load_export(export_dir)
        print(f"{Fore.YELLOW}Export:{Style.RESET_ALL} {export_dir.name}")
        print(f"  Serveur   : {data.get('guild_name', '?')}")
        print(f"  Categorie : {data.get('category_name', '?')}")
        print(f"  Date      : {data.get('exported_at', '?')[:10]}")
        for cat in data.get("categories", []):
            for ch in cat.get("channels", []):
                count = ch.get("message_count", 0)
                print(f"  - #{ch.get('channel_name')} ({count} messages)")
        print()


def show_dossier(export_dirs: list[Path], dossier_name: str) -> None:
    found = False
    for export_dir in export_dirs:
        data = load_export(export_dir)
        for cat in data.get("categories", []):
            for ch in cat.get("channels", []):
                name = ch.get("channel_name") or ""
                if dossier_name.lower() not in name.lower():
                    continue
                found = True
                print(f"\n{Fore.CYAN}=== #{name} ==={Style.RESET_ALL}")
                print(f"Export: {export_dir.name}\n")
                for msg in ch.get("messages", []):
                    print(
                        f"{Fore.YELLOW}[{msg.get('created_at', '')[:10]}]{Style.RESET_ALL} "
                        f"{msg.get('author_name')}"
                    )
                    if msg.get("content"):
                        print(msg["content"][:500])
                    for att in msg.get("attachments", []):
                        print(f"  📎 {att.get('filename')}")
                    for local in msg.get("local_attachments") or []:
                        print(f"  💾 {local}")
                    print()
    if not found:
        animate_error(f"Dossier introuvable: {dossier_name}")


def choose_exports(all_exports: list[Path]) -> list[Path]:
    if not all_exports:
        animate_error(f"Aucun export trouve dans {OUTPUT_DIR.resolve()}")
        return []

    animate_section_title("Exports disponibles")
    print("  0. Tous les exports")
    for i, export in enumerate(all_exports, 1):
        print(f"  {i}. {export.name}")

    choice = input("\nChoix (Entree = dernier export): ").strip()
    if not choice:
        return [all_exports[0]]
    if choice == "0":
        return all_exports
    if choice.isdigit() and 1 <= int(choice) <= len(all_exports):
        return [all_exports[int(choice) - 1]]

    animate_warning("Choix invalide, utilisation du dernier export.")
    return [all_exports[0]]


def save_search_results(hits: list[SearchHit], query: str, output_path: Path) -> None:
    lines = [f"Recherche: {query}", f"Resultats: {len(hits)}", ""]
    for i, hit in enumerate(hits, 1):
        lines.extend(
            [
                f"[{i}] {hit.source} | #{hit.channel_name}",
                f"Auteur: {hit.author_name} | {hit.created_at}",
                hit.content or "(pas de texte)",
                f"Fichiers: {', '.join(hit.attachments) or '-'}",
                f"Export: {hit.export_dir.name}",
                "-" * 40,
            ]
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")
    animate_success(f"Resultats sauvegardes: {output_path}")


def menu_recherche() -> None:
    all_exports = find_exports(OUTPUT_DIR)
    if not all_exports:
        animate_error("Aucun export. Utilise l'option 1 d'abord.")
        return

    selected = choose_exports(all_exports)

    while True:
        animate_menu_open("=== RECHERCHE ===")
        print("  1. Rechercher un mot-cle")
        print("  2. Lister les dossiers")
        print("  3. Ouvrir un dossier")
        print("  4. Changer d'export")
        print("  0. Retour")

        choice = input("\nChoix: ").strip()

        if choice == "1":
            query = input(f"\n{Fore.CYAN}Mot-cle: {Style.RESET_ALL}").strip()
            if not query:
                continue
            dossier = input("Filtrer par dossier (optionnel): ").strip()
            author = input("Filtrer par auteur (optionnel): ").strip()
            run_with_spinner("Analyse des exports", 0.8)
            hits = search_all(selected, query, dossier, author)
            if not hits:
                animate_error("Aucun resultat.")
                continue
            animate_success(f"{len(hits)} resultat(s)")
            for i, hit in enumerate(hits[:50], 1):
                print_hit(i, hit, query)
            if len(hits) > 50:
                print(f"... et {len(hits) - 50} autres.")
            save = input("\nSauvegarder ? (o/n): ").strip().lower()
            if save in {"o", "oui", "y"}:
                out = OUTPUT_DIR / f"recherche_{query[:30].replace(' ', '_')}.txt"
                save_search_results(hits, query, out)
        elif choice == "2":
            list_dossiers(selected)
        elif choice == "3":
            name = input("Nom du dossier: ").strip()
            if name:
                show_dossier(selected, name)
        elif choice == "4":
            selected = choose_exports(all_exports)
        elif choice == "0":
            break
        else:
            animate_invalid_choice()


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def get_vm_unc() -> str:
    if SYNC_VM_UNC:
        return SYNC_VM_UNC.rstrip("\\")
    if not SYNC_VM_HOST:
        return ""
    share = SYNC_VM_SHARE or "tool_oap"
    return f"\\\\{SYNC_VM_HOST}\\{share}"


def vm_label() -> str:
    """Libelle affiche sans exposer l'IP du VPS."""
    return "serveur distant"


def vm_sync_configured() -> bool:
    return SYNC_VM_ENABLED and bool(get_vm_unc()) and bool(SYNC_VM_USER) and bool(SYNC_VM_PASS)


def ensure_vm_connected() -> bool:
    global _vm_share_connected

    if not vm_sync_configured():
        return False

    unc = get_vm_unc()
    if _vm_share_connected and Path(unc).exists():
        return True

    if sys.platform != "win32":
        animate_error("Sync VM SMB: disponible uniquement sous Windows.")
        return False

    creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    result = subprocess.run(
        ["net", "use", unc, SYNC_VM_PASS, f"/user:{SYNC_VM_USER}", "/persistent:no"],
        capture_output=True,
        text=True,
        creationflags=creationflags,
    )
    output = f"{result.stdout}\n{result.stderr}".lower()
    if result.returncode == 0 or "deja" in output or "already" in output or "1219" in output:
        _vm_share_connected = True
        return True

    animate_error("Connexion au serveur distant impossible.")
    print(result.stderr.strip() or result.stdout.strip())
    return False


def load_sync_cache() -> dict:
    if not SYNC_CACHE_FILE.exists():
        return {}
    try:
        return json.loads(SYNC_CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_sync_cache(cache: dict) -> None:
    SYNC_CACHE_FILE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def path_fingerprint(local_path: Path) -> str:
    if local_path.is_file():
        stat = local_path.stat()
        return f"f:{stat.st_mtime_ns}:{stat.st_size}"

    parts: list[str] = []
    for file_path in sorted(local_path.rglob("*")):
        if file_path.is_file():
            stat = file_path.stat()
            rel = file_path.relative_to(local_path)
            parts.append(f"{rel}:{stat.st_mtime_ns}:{stat.st_size}")
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"d:{digest}:{len(parts)}"


def sync_path_to_vm(local_path: Path, quiet: bool = False, force: bool = False) -> bool:
    if not vm_sync_configured():
        return False

    local_path = local_path.resolve()
    if not local_path.exists():
        return False

    if not ensure_vm_connected():
        return False

    try:
        relative = local_path.relative_to(Path.cwd().resolve())
    except ValueError:
        relative = Path(local_path.parent.name) / local_path.name

    cache_key = str(relative).replace("\\", "/")
    fingerprint = path_fingerprint(local_path)
    cache = load_sync_cache()
    if not force and cache.get(cache_key) == fingerprint:
        return True

    remote = Path(get_vm_unc()) / relative
    remote.parent.mkdir(parents=True, exist_ok=True)

    try:
        if local_path.is_dir():
            if remote.exists():
                shutil.rmtree(remote)
            shutil.copytree(local_path, remote)
        else:
            shutil.copy2(local_path, remote)
    except OSError as exc:
        if not quiet:
            animate_error(f"Sync serveur distant echouee: {exc}")
        return False

    cache[cache_key] = fingerprint
    save_sync_cache(cache)

    if not quiet:
        animate_success(f"Donnees sur le {vm_label()}: {relative}")
    return True


def sync_all_to_vm(quiet: bool = False) -> None:
    if not vm_sync_configured():
        if not quiet:
            animate_error("Sync serveur distant desactivee. Configure SYNC_VM_* dans .env")
        return

    if not quiet:
        animate_transition("Synchronisation vers serveur distant", 0.5)
    if not ensure_vm_connected():
        return

    copied = 0
    for base_dir in (DOSSIERS_DIR, OUTPUT_DIR):
        if not base_dir.exists():
            continue
        for item in base_dir.iterdir():
            if sync_path_to_vm(item, quiet=True, force=not quiet):
                copied += 1

    if copied:
        if not quiet:
            animate_success(f"{copied} element(s) synchronise(s) sur le {vm_label()}")
    elif not quiet:
        animate_warning("Rien a synchroniser ou echec de copie.")


def html_page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; background:#1e1f22; color:#dbdee1; margin:0; padding:20px; }}
nav {{ background:#2b2d31; padding:12px 16px; border-radius:8px; margin-bottom:20px; }}
nav a {{ color:#5865f2; text-decoration:none; margin-right:16px; font-weight:600; }}
.card {{ background:#2b2d31; padding:16px; margin:12px 0; border-radius:8px; border-left:4px solid #5865f2; }}
.card small {{ color:#949ba4; }}
pre {{ background:#111214; padding:14px; border-radius:8px; overflow:auto; white-space:pre-wrap; word-break:break-word; }}
a {{ color:#00a8fc; }}
.badge {{ background:#5865f2; color:white; padding:2px 8px; border-radius:4px; font-size:12px; }}
</style></head>
<body>
<nav>
  <a href="/">Accueil</a>
  <a href="/dossiers">Dossiers crees</a>
  <a href="/exports">Exports Discord</a>
</nav>
<h1>{html.escape(title)}</h1>
{body}
</body></html>"""


def resolve_child_dir(base: Path, name: str) -> Path | None:
    if not name or ".." in name or name.startswith(("/", "\\")):
        return None
    try:
        target = (base / urllib.parse.unquote(name)).resolve()
        base_resolved = base.resolve()
        if target == base_resolved or base_resolved in target.parents:
            return target if target.is_dir() else None
    except OSError:
        return None
    return None


class DonneesWebHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return

    def _send_html(self, content: str, status: int = 200) -> None:
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self._send_html(html_page("Erreur", "<p>Fichier introuvable.</p>"), 404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="{path.name}"',
        )
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/":
            nb_dossiers = len(find_local_dossiers())
            nb_exports = len(find_exports(OUTPUT_DIR))
            body = f"""
            <p>Consulte les donnees TOOL OAP depuis ce PC ou un autre sur le meme reseau.</p>
            <div class="card"><strong>Dossiers crees</strong><br>{nb_dossiers} dossier(s)</div>
            <div class="card"><strong>Exports Discord</strong><br>{nb_exports} export(s)</div>
            """
            self._send_html(html_page("TOOL OAP - Donnees", body))
            return

        if path == "/dossiers":
            items = []
            for dossier_dir in find_local_dossiers():
                data = load_dossier_meta(dossier_dir)
                label = dossier_label(data)
                encoded = urllib.parse.quote(dossier_dir.name)
                items.append(
                    f'<div class="card"><a href="/dossier/{encoded}"><strong>{html.escape(label)}</strong></a>'
                    f'<br><small>{html.escape(dossier_dir.name)} | {data.get("created_at", "")[:10]}</small></div>'
                )
            body = "".join(items) or "<p>Aucun dossier cree.</p>"
            self._send_html(html_page("Dossiers crees", body))
            return

        if path.startswith("/dossier/"):
            folder_name = path.removeprefix("/dossier/")
            dossier_dir = resolve_child_dir(DOSSIERS_DIR, folder_name)
            if not dossier_dir:
                self._send_html(html_page("Erreur", "<p>Dossier introuvable.</p>"), 404)
                return
            data = load_dossier_meta(dossier_dir)
            content = html.escape(read_dossier_content(dossier_dir, data))
            txt_path = get_dossier_text_path(dossier_dir, data)
            file_link = ""
            if txt_path.exists():
                file_link = (
                    f'<p><a href="/telecharger/dossiers/{urllib.parse.quote(dossier_dir.name)}'
                    f'/{urllib.parse.quote(txt_path.name)}">Telecharger {html.escape(txt_path.name)}</a></p>'
                )
            meta = html.escape(json.dumps(data, ensure_ascii=False, indent=2))
            body = (
                f"<p><span class='badge'>#{html.escape(data.get('channel_name', '?'))}</span></p>"
                f"{file_link}<h2>Contenu</h2><pre>{content or '(vide)'}</pre>"
                f"<h2>Metadonnees</h2><pre>{meta}</pre>"
            )
            self._send_html(html_page(dossier_label(data), body))
            return

        if path == "/exports":
            items = []
            for export_dir in find_exports(OUTPUT_DIR):
                encoded = urllib.parse.quote(export_dir.name)
                items.append(
                    f'<div class="card"><a href="/export/{encoded}"><strong>{html.escape(export_dir.name)}</strong></a></div>'
                )
            body = "".join(items) or "<p>Aucun export.</p>"
            self._send_html(html_page("Exports Discord", body))
            return

        if path.startswith("/export/"):
            folder_name = path.removeprefix("/export/")
            export_dir = resolve_child_dir(OUTPUT_DIR, folder_name)
            if not export_dir:
                self._send_html(html_page("Erreur", "<p>Export introuvable.</p>"), 404)
                return
            resume = export_dir / "resume.txt"
            json_path = export_dir / "export_complet.json"
            parts = [f"<p><strong>{html.escape(export_dir.name)}</strong></p>"]
            if resume.exists():
                parts.append(f"<h2>Resume</h2><pre>{html.escape(resume.read_text(encoding='utf-8'))}</pre>")
            if json_path.exists():
                enc = urllib.parse.quote(export_dir.name)
                parts.append(
                    f'<p><a href="/telecharger/exports/{enc}/export_complet.json">Telecharger JSON</a> | '
                    f'<a href="/telecharger/exports/{enc}/export_messages.csv">Telecharger CSV</a></p>'
                )
            self._send_html(html_page("Export", "".join(parts)))
            return

        if path.startswith("/telecharger/"):
            parts = path.split("/")
            if len(parts) < 5:
                self._send_html(html_page("Erreur", "<p>Lien invalide.</p>"), 404)
                return
            kind, folder_name, file_name = parts[2], parts[3], parts[4]
            base = DOSSIERS_DIR if kind == "dossiers" else OUTPUT_DIR if kind == "exports" else None
            if not base:
                self._send_html(html_page("Erreur", "<p>Type invalide.</p>"), 404)
                return
            parent = resolve_child_dir(base, folder_name)
            if not parent:
                self._send_html(html_page("Erreur", "<p>Dossier introuvable.</p>"), 404)
                return
            file_path = parent / urllib.parse.unquote(file_name)
            if not file_path.resolve().is_file() or parent.resolve() not in file_path.resolve().parents:
                self._send_html(html_page("Erreur", "<p>Fichier introuvable.</p>"), 404)
                return
            self._send_file(file_path)
            return

        self._send_html(html_page("404", "<p>Page introuvable.</p>"), 404)


def start_web_server() -> None:
    DOSSIERS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    server = ThreadingHTTPServer((WEB_HOST, WEB_PORT), DonneesWebHandler)
    local_ip = get_local_ip()

    animate_success("Serveur web demarre !")
    print(f"\n{Fore.CYAN}  PC principal : {Style.RESET_ALL} http://127.0.0.1:{WEB_PORT}")
    print(f"{Fore.CYAN}  Autre PC     : {Style.RESET_ALL} http://{local_ip}:{WEB_PORT}")
    print(f"{Fore.YELLOW}  Arret : Ctrl+C{Style.RESET_ALL}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        animate_warning("Serveur arrete.")
    finally:
        server.server_close()


def export_all_data_zip() -> Path | None:
    DOSSIERS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = Path.cwd() / f"tool_oap_donnees_{timestamp}.zip"

    animate_transition("Creation du ZIP", 0.5)
    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for root_name, root_dir in (("dossiers", DOSSIERS_DIR), ("export_discord", OUTPUT_DIR)):
            if not root_dir.exists():
                continue
            for file_path in root_dir.rglob("*"):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(root_dir.parent))
                    file_count += 1

    if file_count == 0:
        zip_path.unlink(missing_ok=True)
        animate_error("Aucune donnee a exporter.")
        return None

    animate_success(f"ZIP cree: {zip_path.name} ({file_count} fichiers)")
    print(f"  Copie ce fichier sur l'autre PC et decompresse-le dans le dossier du tool.")
    if vm_sync_configured():
        sync_path_to_vm(zip_path)
    return zip_path


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        os.system(f'open "{path}"')
    else:
        os.system(f'xdg-open "{path}"')


def menu_voir_donnees() -> None:
    while True:
        animate_menu_open("=== VOIR LES DONNEES ===")
        print("  1. Serveur web (PC principal + autres PC)")
        print("  2. Exporter tout en ZIP (autre PC)")
        print("  3. Ouvrir dossier 'dossiers'")
        print("  4. Ouvrir dossier 'export_discord'")
        if vm_sync_configured():
            print("  5. Synchroniser tout vers le serveur distant")
        print("  0. Retour")

        choice = input("\nChoix: ").strip()

        if choice == "1":
            start_web_server()
        elif choice == "2":
            export_all_data_zip()
        elif choice == "3":
            open_folder(DOSSIERS_DIR.resolve())
            animate_info(f"Dossier ouvert: {DOSSIERS_DIR.resolve()}")
        elif choice == "4":
            open_folder(OUTPUT_DIR.resolve())
            animate_info(f"Dossier ouvert: {OUTPUT_DIR.resolve()}")
        elif choice == "5" and vm_sync_configured():
            sync_all_to_vm()
        elif choice == "0":
            break
        else:
            animate_invalid_choice()


def tool_menu(user: User) -> bool:
    while True:
        animate_menu_open(f"=== MENU ({user.username}) ===")
        print(f"  Discord: {discord_token_status(DATA_DIR)}")
        print("  1. Exporter Discord")
        print("  2. Rechercher dans les dossiers")
        print("  3. Creer un dossier")
        print("  4. Gerer les dossiers crees")
        print("  5. Mon compte")
        print("  6. Deconnexion")
        print("  7. Voir les donnees (web / reseau)")
        print("  8. Verifier mise a jour (GitHub)")
        print(f"  Version: v{VERSION}")
        print("  0. Quitter")

        choice = input("\nChoix: ").strip()

        if choice == "1":
            animate_transition("Lancement export Discord", 0.4)
            asyncio.run(export_discord())
        elif choice == "2":
            menu_recherche()
        elif choice == "3":
            try:
                menu_creer_dossier(user)
            except KeyboardInterrupt:
                animate_warning("Creation annulee.")
        elif choice == "4":
            try:
                menu_gerer_dossiers(user)
            except KeyboardInterrupt:
                animate_warning("Operation annulee.")
        elif choice == "5":
            menu_compte(user)
        elif choice == "6":
            animate_warning("Deconnecte.")
            return True
        elif choice == "7":
            menu_voir_donnees()
        elif choice == "8":
            run_update_menu(
                GITHUB_REPO,
                DATA_DIR,
                is_frozen(),
                AUTO_MODE,
                UPDATE_DIR,
                animate_success,
                animate_error,
                animate_info,
                animate_warning,
                animate_transition,
                safe_input,
            )
        elif choice == "0":
            animate_info("Au revoir.")
            return False
        else:
            animate_invalid_choice()


def safe_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", name)
    return cleaned.strip() or "sans_nom"


def message_to_dict(msg: discord.Message) -> dict:
    return {
        "id": str(msg.id),
        "author_id": str(msg.author.id),
        "author_name": str(msg.author),
        "content": msg.content,
        "created_at": msg.created_at.isoformat(),
        "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
        "attachments": [
            {
                "filename": a.filename,
                "url": a.url,
                "size": a.size,
                "content_type": a.content_type,
            }
            for a in msg.attachments
        ],
        "embeds": [e.to_dict() for e in msg.embeds],
        "reactions": [
            {"emoji": str(r.emoji), "count": r.count} for r in msg.reactions
        ],
        "pinned": msg.pinned,
        "reference_message_id": str(msg.reference.message_id)
        if msg.reference and msg.reference.message_id
        else None,
    }


async def fetch_all_messages(channel: discord.abc.Messageable) -> list[discord.Message]:
    messages: list[discord.Message] = []
    async for msg in channel.history(limit=None, oldest_first=True):
        messages.append(msg)
    return messages


async def export_channel(
    channel: discord.abc.Messageable,
    category_name: str,
    attachments_dir: Path,
    run_dir: Path,
) -> dict:
    label = getattr(channel, "name", str(channel.id))
    animate_pulse_text(f"Export #{label}", cycles=1)

    messages = await fetch_all_messages(channel)
    channel_attachments = attachments_dir / safe_filename(label)

    exported_messages = []
    for msg in messages:
        data = message_to_dict(msg)
        if msg.attachments:
            channel_attachments.mkdir(parents=True, exist_ok=True)
            local_files = []
            for att in msg.attachments:
                local_path = channel_attachments / f"{msg.id}_{safe_filename(att.filename)}"
                try:
                    await att.save(local_path)
                    local_files.append(str(local_path.relative_to(run_dir)))
                except Exception as exc:
                    local_files.append(f"ERREUR: {exc}")
            data["local_attachments"] = local_files
        exported_messages.append(data)

    return {
        "channel_id": str(channel.id),
        "channel_name": getattr(channel, "name", None),
        "channel_type": str(channel.type),
        "category": category_name,
        "message_count": len(exported_messages),
        "messages": exported_messages,
    }


async def export_channel_tree(
    channel: discord.abc.GuildChannel,
    category_name: str,
    attachments_dir: Path,
    run_dir: Path,
) -> list[dict]:
    results: list[dict] = []

    if isinstance(channel, discord.ForumChannel):
        threads = list(channel.threads)
        async for thread in channel.archived_threads(limit=None):
            threads.append(thread)
        for thread in threads:
            if thread.id in EXCLUDED_CHANNELS:
                continue
            results.append(
                await export_channel(thread, category_name, attachments_dir, run_dir)
            )
        return results

    results.append(await export_channel(channel, category_name, attachments_dir, run_dir))

    for thread in channel.threads:
        if thread.id in EXCLUDED_CHANNELS:
            continue
        results.append(
            await export_channel(thread, category_name, attachments_dir, run_dir)
        )

    async for thread in channel.archived_threads(limit=None):
        if thread.id in EXCLUDED_CHANNELS:
            continue
        results.append(
            await export_channel(thread, category_name, attachments_dir, run_dir)
        )

    return results


def write_csv(export_data: dict, csv_path: Path) -> None:
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            [
                "categorie",
                "salon",
                "salon_id",
                "message_id",
                "auteur",
                "auteur_id",
                "date",
                "contenu",
                "pieces_jointes",
                "epingle",
            ]
        )
        for cat in export_data["categories"]:
            for ch in cat["channels"]:
                for msg in ch["messages"]:
                    attachments = " | ".join(
                        a.get("filename", "") for a in msg.get("attachments", [])
                    )
                    writer.writerow(
                        [
                            ch["category"],
                            ch["channel_name"],
                            ch["channel_id"],
                            msg["id"],
                            msg["author_name"],
                            msg["author_id"],
                            msg["created_at"],
                            msg["content"].replace("\n", " "),
                            attachments,
                            msg["pinned"],
                        ]
                    )


def find_category(
    client: discord.Client, category_id: int
) -> tuple[discord.Guild | None, discord.CategoryChannel | None]:
    guilds = client.guilds
    if GUILD_ID is not None:
        guild = client.get_guild(GUILD_ID)
        guilds = [guild] if guild else []

    for guild in guilds:
        if guild is None:
            continue
        channel = guild.get_channel(category_id)
        if isinstance(channel, discord.CategoryChannel):
            return guild, channel
    return None, None


async def export_category(
    category: discord.CategoryChannel,
    attachments_dir: Path,
    run_dir: Path,
) -> tuple[dict, int, int]:
    animate_section_title(f"Categorie: {category.name} ({category.id})")
    category_entry = {
        "category_id": str(category.id),
        "category_name": category.name,
        "position": category.position,
        "channels": [],
    }

    total_channels = 0
    total_messages = 0

    channels = sorted(
        [
            ch
            for ch in category.channels
            if ch.id not in EXCLUDED_CHANNELS and isinstance(ch, EXPORTABLE)
        ],
        key=lambda c: c.position,
    )
    total_ch = len(channels)

    for index, channel in enumerate(channels, 1):
        animate_progress(index, total_ch, "Export salons")
        for ch_data in await export_channel_tree(
            channel, category.name, attachments_dir, run_dir
        ):
            category_entry["channels"].append(ch_data)
            total_messages += ch_data["message_count"]
            total_channels += 1

    return category_entry, total_channels, total_messages


async def run_export(
    client: discord.Client,
    guild: discord.Guild,
    category: discord.CategoryChannel,
) -> None:
    animate_info(f"Serveur: {guild.name} ({guild.id})")
    run_with_spinner("Preparation de l'export", 0.5)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = (
        OUTPUT_DIR
        / f"{safe_filename(guild.name)}_{safe_filename(category.name)}_{timestamp}"
    )
    attachments_dir = run_dir / "pieces_jointes"
    run_dir.mkdir(parents=True, exist_ok=True)

    export_data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "guild_id": str(guild.id),
        "guild_name": guild.name,
        "category_id": str(category.id),
        "category_name": category.name,
        "excluded_channels": [str(c) for c in sorted(EXCLUDED_CHANNELS)],
        "categories": [],
    }

    category_entry, total_channels, total_messages = await export_category(
        category, attachments_dir, run_dir
    )
    if category_entry["channels"]:
        export_data["categories"].append(category_entry)

    export_data["summary"] = {
        "categories_exported": len(export_data["categories"]),
        "channels_exported": total_channels,
        "messages_exported": total_messages,
    }

    json_path = run_dir / "export_complet.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    csv_path = run_dir / "export_messages.csv"
    write_csv(export_data, csv_path)

    summary_path = run_dir / "resume.txt"
    with summary_path.open("w", encoding="utf-8") as f:
        f.write(f"Serveur: {guild.name}\n")
        f.write(f"Categorie: {category.name} ({category.id})\n")
        f.write(f"Date export: {export_data['exported_at']}\n")
        f.write(f"Categories: {export_data['summary']['categories_exported']}\n")
        f.write(f"Salons: {export_data['summary']['channels_exported']}\n")
        f.write(f"Messages: {export_data['summary']['messages_exported']}\n")
        f.write(f"Salons exclus: {', '.join(export_data['excluded_channels'])}\n\n")
        for cat in export_data["categories"]:
            f.write(f"\n[{cat['category_name']}]\n")
            for ch in cat["channels"]:
                f.write(
                    f"  - #{ch['channel_name']} ({ch['channel_id']}): "
                    f"{ch['message_count']} messages\n"
                )

    animate_result_box(
        "EXPORT TERMINE",
        [
            f"Dossier: {run_dir.resolve()}",
            f"JSON: {json_path.name}",
            f"CSV:  {csv_path.name}",
            f"Messages: {total_messages} | Salons: {total_channels}",
        ],
    )
    sync_path_to_vm(run_dir)


async def export_discord_action(client: discord.Client) -> None:
    animate_pulse_text(f"Recherche categorie {CATEGORY_ID}")
    guild, category, error = await get_guild_category(client)
    if error:
        animate_error("Categorie introuvable.")
        print(error)
        return
    await run_export(client, guild, category)


async def export_discord() -> None:
    await run_discord_task(export_discord_action)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    animate_banner()

    run_startup_automation(
        github_repo=GITHUB_REPO,
        app_dir=DATA_DIR,
        frozen=is_frozen(),
        auto_update=AUTO_UPDATE_ON_START,
        auto_mode=AUTO_MODE,
        auto_sync=AUTO_SYNC_ON_START and vm_sync_configured(),
        update_check_hours=UPDATE_CHECK_HOURS,
        install_dir=UPDATE_DIR,
        sync_callback=sync_all_to_vm,
        update_callback=auto_check_on_start,
        animate_info=animate_info,
        animate_success=animate_success,
        animate_warning=animate_warning,
    )

    while True:
        user = login_screen()
        if not user:
            animate_warning("Fermeture du programme.")
            break
        animate_pulse_text(f"Bienvenue {user.username}")
        if not tool_menu(user):
            break

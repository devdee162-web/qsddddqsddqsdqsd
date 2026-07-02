"""Chemins et chargement config sans .env a cote de l'exe."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from app_config import PUBLIC_DEFAULTS
from updater import DEFAULT_GITHUB_REPO, github_repo_configured

try:
    from _embedded_secrets import SYNC_VM_HOST as EMBEDDED_VM_HOST
    from _embedded_secrets import SYNC_VM_PASS as EMBEDDED_VM_PASS
except ImportError:
    EMBEDDED_VM_HOST = ""
    EMBEDDED_VM_PASS = ""

CONFIG_NAME = "config.env"
DATA_DIR_NAME = "TOOL_OAP"


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def get_install_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_data_dir() -> Path:
    if is_frozen():
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / DATA_DIR_NAME
    else:
        base = Path(__file__).resolve().parent
    base.mkdir(parents=True, exist_ok=True)
    return base


def config_path(data_dir: Path) -> Path:
    return data_dir / CONFIG_NAME


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


def _write_env_file(path: Path, values: dict[str, str]) -> None:
    lines = [f"{key}={value}" for key, value in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _migration_sources(install_dir: Path, data_dir: Path) -> list[Path]:
    candidates = [
        data_dir / ".env",
        data_dir / CONFIG_NAME,
        install_dir / ".env",
        install_dir.parent / ".env",
        install_dir / "config.example.env",
        install_dir.parent / "config.example.env",
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        if not path.exists():
            continue
        resolved = str(path.resolve())
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique


def build_config_values(install_dir: Path, data_dir: Path) -> dict[str, str]:
    values = dict(PUBLIC_DEFAULTS)

    if EMBEDDED_VM_PASS:
        values["SYNC_VM_PASS"] = EMBEDDED_VM_PASS
    if EMBEDDED_VM_HOST:
        values["SYNC_VM_HOST"] = EMBEDDED_VM_HOST

    for source in _migration_sources(install_dir, data_dir):
        values.update(_parse_env_file(source))

    if not github_repo_configured(values.get("GITHUB_REPO", "")):
        values["GITHUB_REPO"] = DEFAULT_GITHUB_REPO

    return values


def ensure_config(install_dir: Path, data_dir: Path) -> Path:
    cfg = config_path(data_dir)
    values = build_config_values(install_dir, data_dir)
    _write_env_file(cfg, values)
    return cfg


def apply_config_to_environ(values: dict[str, str]) -> None:
    for key, value in values.items():
        if value:
            os.environ[key] = value


def ensure_data_folders(data_dir: Path) -> None:
    for name in ("dossiers", "export_discord"):
        (data_dir / name).mkdir(parents=True, exist_ok=True)

    accounts = data_dir / "accounts.json"
    if not accounts.exists():
        install_dir = get_install_dir()
        for source in (install_dir / "accounts.json", install_dir.parent / "accounts.json"):
            if source.exists():
                shutil.copy2(source, accounts)
                break


def bootstrap() -> tuple[Path, Path]:
    install_dir = get_install_dir()
    data_dir = get_data_dir()
    cfg = ensure_config(install_dir, data_dir)
    values = _parse_env_file(cfg)
    apply_config_to_environ(values)
    ensure_data_folders(data_dir)
    os.chdir(data_dir)
    return install_dir, data_dir

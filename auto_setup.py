"""Configuration et taches automatiques au demarrage."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from updater import DEFAULT_GITHUB_REPO, github_repo_configured

ENV_DEFAULTS = {
    "GITHUB_REPO": DEFAULT_GITHUB_REPO,
    "AUTO_UPDATE_ON_START": "true",
    "AUTO_MODE": "true",
    "AUTO_SYNC_ON_START": "false",
    "UPDATE_CHECK_HOURS": "24",
    "SYNC_VM_ENABLED": "false",
    "OUTPUT_DIR": "export_discord",
    "DOSSIERS_DIR": "dossiers",
    "ACCOUNTS_FILE": "accounts.json",
}


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def _env_value(lines: list[str], key: str) -> str:
    prefix = f"{key}="
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def _set_or_append(lines: list[str], key: str, value: str) -> list[str]:
    prefix = f"{key}="
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = f"{prefix}{value}"
            return lines
    if lines and lines[-1].strip():
        lines.append("")
    lines.append(f"{prefix}{value}")
    return lines


def _find_example(app_dir: Path) -> Path | None:
    for candidate in (app_dir / "config.example.env", app_dir.parent / "config.example.env"):
        if candidate.exists():
            return candidate
    return None


def ensure_env_file(app_dir: Path) -> Path:
    env_path = app_dir / ".env"
    parent_env = app_dir.parent / ".env"

    if parent_env.exists() and parent_env.resolve() != env_path.resolve():
        shutil.copy2(parent_env, env_path)
    elif not env_path.exists():
        example = _find_example(app_dir)
        if example:
            shutil.copy2(example, env_path)
        else:
            env_path.write_text(
                "\n".join(f"{key}={value}" for key, value in ENV_DEFAULTS.items()) + "\n",
                encoding="utf-8",
            )

    lines = _read_lines(env_path)
    for key, value in ENV_DEFAULTS.items():
        current = _env_value(lines, key)
        if not current or (key == "GITHUB_REPO" and not github_repo_configured(current)):
            lines = _set_or_append(lines, key, value)

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return env_path


def ensure_runtime_files(app_dir: Path) -> None:
    parent_accounts = app_dir.parent / "accounts.json"
    local_accounts = app_dir / "accounts.json"
    if parent_accounts.exists() and not local_accounts.exists():
        shutil.copy2(parent_accounts, local_accounts)

    for folder_name in ("dossiers", "export_discord"):
        (app_dir / folder_name).mkdir(parents=True, exist_ok=True)


def prepare_environment(app_dir: Path) -> None:
    ensure_env_file(app_dir)
    ensure_runtime_files(app_dir)


def env_flag(name: str, default: str = "false") -> bool:
    from dotenv import dotenv_values

    app_dir = Path.cwd()
    values = dotenv_values(app_dir / ".env")
    raw = str(values.get(name, default)).strip().lower()
    return raw in {"1", "true", "oui", "yes", "on"}


def run_startup_automation(
    *,
    github_repo: str,
    app_dir: Path,
    frozen: bool,
    auto_update: bool,
    auto_mode: bool,
    auto_sync: bool,
    update_check_hours: int,
    sync_callback,
    update_callback,
    animate_info,
    animate_success,
    animate_warning,
) -> None:
    if auto_sync:
        try:
            sync_callback(quiet=True)
        except Exception:
            pass

    if not auto_update:
        return

    try:
        update_callback(
            github_repo=github_repo,
            app_dir=app_dir,
            frozen=frozen,
            auto_install=auto_mode,
            interval_hours=update_check_hours,
            animate_info=animate_info,
            animate_success=animate_success,
            animate_warning=animate_warning,
        )
    except Exception:
        if auto_mode:
            animate_warning("Mise a jour auto ignoree (offline ou release indisponible).")

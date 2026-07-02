"""Configuration et taches automatiques au demarrage."""

from __future__ import annotations

from pathlib import Path

from app_paths import bootstrap


def prepare_environment() -> tuple[Path, Path]:
    return bootstrap()


def run_startup_automation(
    *,
    github_repo: str,
    app_dir: Path,
    frozen: bool,
    auto_update: bool,
    auto_mode: bool,
    auto_sync: bool,
    update_check_hours: int,
    install_dir: Path | None,
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
            enabled=True,
            auto_install=auto_mode,
            interval_hours=update_check_hours,
            install_dir=install_dir,
            animate_info=animate_info,
            animate_success=animate_success,
            animate_warning=animate_warning,
        )
    except Exception:
        if auto_mode:
            animate_warning("Mise a jour auto ignoree (offline ou release indisponible).")

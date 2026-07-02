"""Verification et installation des mises a jour via GitHub Releases."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from version import VERSION

USER_AGENT = "TOOL-OAP-Updater"
CACHE_NAME = ".tool_oap_cache.json"
DEFAULT_GITHUB_REPO = "devdee162-web/qsddddqsddqsdqsd"


def cache_path(app_dir: Path) -> Path:
    return app_dir / CACHE_NAME


def load_cache(app_dir: Path) -> dict:
    path = cache_path(app_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(app_dir: Path, data: dict) -> None:
    cache_path(app_dir).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def should_check_updates(app_dir: Path, interval_hours: int) -> bool:
    cache = load_cache(app_dir)
    last_check = float(cache.get("last_check_ts", 0))
    return (time.time() - last_check) >= max(1, interval_hours) * 3600


def already_has_version(app_dir: Path, remote_tag: str) -> bool:
    cache = load_cache(app_dir)
    return cache.get("installed_version") == remote_tag


def parse_version(raw: str) -> tuple[int, ...]:
    cleaned = raw.strip().lstrip("vV")
    parts: list[int] = []
    for chunk in re.split(r"[.\-+]", cleaned):
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            break
    return tuple(parts) if parts else (0,)


def is_newer(remote: str, local: str) -> bool:
    return parse_version(remote) > parse_version(local)


def github_repo_configured(github_repo: str) -> bool:
    repo = github_repo.strip().strip('"').strip("'")
    return bool(repo and "/" in repo and " " not in repo)


def read_env_value(app_dir: Path, key: str) -> str:
    for name in ("config.env", ".env"):
        env_file = app_dir / name
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name_key, value = stripped.split("=", 1)
            if name_key.strip() == key:
                return value.strip().strip('"').strip("'")
    return ""


def resolve_github_repo(github_repo: str, app_dir: Path) -> str:
    for candidate in (
        github_repo,
        read_env_value(app_dir, "GITHUB_REPO"),
        os.getenv("GITHUB_REPO", ""),
    ):
        repo = str(candidate or "").strip().strip('"').strip("'")
        if github_repo_configured(repo):
            return repo

    try:
        from dotenv import dotenv_values

        repo = str(dotenv_values(app_dir / "config.env").get("GITHUB_REPO", "")).strip()
        if github_repo_configured(repo):
            return repo
        repo = str(dotenv_values(app_dir / ".env").get("GITHUB_REPO", "")).strip()
        if github_repo_configured(repo):
            return repo
    except Exception:
        pass

    return DEFAULT_GITHUB_REPO


def fetch_latest_release(github_repo: str) -> dict | None:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
    }

    latest_url = f"https://api.github.com/repos/{github_repo}/releases/latest"
    request = urllib.request.Request(latest_url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    except urllib.error.URLError:
        return None

    list_url = f"https://api.github.com/repos/{github_repo}/releases?per_page=10"
    request = urllib.request.Request(list_url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            releases = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None

    for release in releases:
        if release.get("assets"):
            return release
    return releases[0] if releases else None


def find_exe_asset(release: dict) -> dict | None:
    for asset in release.get("assets", []):
        name = asset.get("name", "").lower()
        if name.endswith(".exe") and "tool_oap" in name:
            return asset
    for asset in release.get("assets", []):
        if asset.get("name", "").lower().endswith(".exe"):
            return asset
    return None


def download_file(url: str, dest: Path, label: str = "Telechargement") -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 1024 * 256
        with dest.open("wb") as handle:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = min(100, int(downloaded * 100 / total))
                    print(f"\r{label}: {pct}%", end="", flush=True)
    print()


def apply_exe_update(app_dir: Path, new_exe: Path, exe_name: str = "TOOL_OAP.exe") -> None:
    updater_bat = app_dir / "_update_tool_oap.bat"
    script = f"""@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Mise a jour TOOL OAP...
timeout /t 2 /nobreak >nul
if exist "{exe_name}.old" del /f /q "{exe_name}.old"
if exist "{exe_name}" move /y "{exe_name}" "{exe_name}.old"
move /y "{new_exe.name}" "{exe_name}"
echo Relancement...
start "" "{exe_name}"
del /f /q "%~f0"
"""
    updater_bat.write_text(script, encoding="utf-8")
    subprocess.Popen(
        ["cmd", "/c", str(updater_bat)],
        cwd=str(app_dir),
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )
    sys.exit(0)


def check_update_info(github_repo: str, app_dir: Path | None = None) -> tuple[bool, str, dict | None]:
    repo = resolve_github_repo(github_repo, app_dir or Path.cwd())
    release = fetch_latest_release(repo)
    if not release:
        return False, f"Aucune release GitHub trouvee pour {repo}.", None

    tag = release.get("tag_name", "?")
    if is_newer(tag, VERSION):
        return True, f"Mise a jour disponible: v{VERSION} -> {tag}", release

    return False, f"Version a jour (v{VERSION})", release


def install_update(
    github_repo: str,
    app_dir: Path,
    release: dict | None = None,
    frozen: bool = False,
    install_dir: Path | None = None,
) -> bool:
    repo = resolve_github_repo(github_repo, app_dir)
    release = release or fetch_latest_release(repo)
    if not release:
        return False

    remote_tag = release.get("tag_name", "?")
    if already_has_version(app_dir, remote_tag):
        return False

    target_dir = install_dir or app_dir

    if frozen:
        asset = find_exe_asset(release)
        if not asset:
            return False
        new_exe = target_dir / "TOOL_OAP.exe.new"
        download_file(asset["browser_download_url"], new_exe, "Telechargement EXE")
        cache = load_cache(app_dir)
        cache["installed_version"] = remote_tag
        cache["last_check_ts"] = time.time()
        cache["last_remote_tag"] = remote_tag
        save_cache(app_dir, cache)
        apply_exe_update(target_dir, new_exe)
        return True

    url = release.get("zipball_url") or release.get("tarball_url")
    if not url:
        return False

    archive = app_dir / "_update_source.zip"
    download_file(url, archive, "Telechargement sources")
    import zipfile

    extract_dir = app_dir / "_update_extract"
    if extract_dir.exists():
        import shutil

        shutil.rmtree(extract_dir)
    extract_dir.mkdir()

    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(extract_dir)

    root_dirs = [p for p in extract_dir.iterdir() if p.is_dir()]
    if not root_dirs:
        return False

    source_root = root_dirs[0]
    import shutil

    for name in (
        "export_discord.py",
        "version.py",
        "updater.py",
        "auto_setup.py",
        "requirements.txt",
        "lancer_export.bat",
        "build_exe.bat",
        "TOOL_OAP.spec",
    ):
        src = source_root / name
        if src.exists():
            shutil.copy2(src, app_dir / name)

    shutil.rmtree(extract_dir, ignore_errors=True)
    archive.unlink(missing_ok=True)

    cache = load_cache(app_dir)
    cache["installed_version"] = remote_tag
    cache["last_check_ts"] = time.time()
    cache["last_remote_tag"] = remote_tag
    save_cache(app_dir, cache)
    return True


def perform_update_check(
    *,
    github_repo: str,
    app_dir: Path,
    frozen: bool,
    auto_install: bool,
    interval_hours: int,
    force: bool,
    silent_if_uptodate: bool,
    install_dir: Path | None = None,
    animate_info,
    animate_success,
    animate_warning,
    safe_input=None,
) -> None:
    repo = resolve_github_repo(github_repo, app_dir)

    if not force and not should_check_updates(app_dir, interval_hours):
        return

    try:
        available, message, release = check_update_info(repo, app_dir)
    except Exception as exc:
        if not silent_if_uptodate:
            animate_info(f"Mise a jour ignoree: {exc}")
        return

    remote_tag = release.get("tag_name", "?") if release else "?"
    cache = load_cache(app_dir)
    cache["last_check_ts"] = time.time()
    cache["last_remote_tag"] = remote_tag
    cache["update_available"] = available
    save_cache(app_dir, cache)

    if not available:
        if not silent_if_uptodate:
            animate_info(message)
        return

    if already_has_version(app_dir, remote_tag):
        return

    if auto_install:
        animate_warning(f"{message} - installation auto...")
        try:
            if install_update(
                repo, app_dir, release, frozen=frozen, install_dir=install_dir
            ):
                if not frozen:
                    animate_success("Sources mises a jour. Relance le tool.")
            else:
                animate_warning("Mise a jour auto impossible (EXE absent sur GitHub).")
        except Exception as exc:
            animate_warning(f"Mise a jour auto echouee: {exc}")
        return

    animate_warning(message)
    if safe_input is None:
        return

    confirm = safe_input("Installer la mise a jour ? (o/n): ")
    if confirm and confirm.lower() in {"o", "oui", "y", "yes"}:
        try:
            if install_update(
                repo, app_dir, release, frozen=frozen, install_dir=install_dir
            ):
                if not frozen:
                    animate_success("Sources mises a jour. Relance le tool.")
        except Exception as exc:
            animate_warning(f"Erreur: {exc}")


def run_update_menu(
    github_repo: str,
    app_dir: Path,
    frozen: bool,
    auto_mode: bool,
    install_dir: Path | None,
    animate_success,
    animate_error,
    animate_info,
    animate_warning,
    animate_transition,
    safe_input,
) -> None:
    animate_transition("Verification GitHub", 0.4)
    perform_update_check(
        github_repo=github_repo,
        app_dir=app_dir,
        frozen=frozen,
        auto_install=auto_mode,
        interval_hours=24,
        force=True,
        silent_if_uptodate=False,
        install_dir=install_dir,
        animate_info=animate_info,
        animate_success=animate_success,
        animate_warning=animate_warning,
        safe_input=None if auto_mode else safe_input,
    )


def auto_check_on_start(
    github_repo: str,
    app_dir: Path,
    frozen: bool,
    enabled: bool,
    auto_install: bool,
    interval_hours: int,
    install_dir: Path | None,
    animate_info,
    animate_success,
    animate_warning,
) -> None:
    if not enabled:
        return

    perform_update_check(
        github_repo=github_repo,
        app_dir=app_dir,
        frozen=frozen,
        auto_install=auto_install,
        interval_hours=interval_hours,
        force=False,
        silent_if_uptodate=True,
        install_dir=install_dir,
        animate_info=animate_info,
        animate_success=animate_success,
        animate_warning=animate_warning,
    )

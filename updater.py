"""Verification et installation des mises a jour via GitHub Releases."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from version import VERSION

USER_AGENT = "TOOL-OAP-Updater"


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
    return bool(github_repo and "/" in github_repo and " " not in github_repo)


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


def check_update_info(github_repo: str) -> tuple[bool, str, dict | None]:
    if not github_repo_configured(github_repo):
        return False, "GITHUB_REPO non configure dans .env", None

    release = fetch_latest_release(github_repo)
    if not release:
        return False, "Aucune release GitHub trouvee.", None

    tag = release.get("tag_name", "?")
    if is_newer(tag, VERSION):
        return True, f"Mise a jour disponible: v{VERSION} -> {tag}", release

    return False, f"Version a jour (v{VERSION})", release


def install_update(
    github_repo: str,
    app_dir: Path,
    release: dict | None = None,
    frozen: bool = False,
) -> bool:
    release = release or fetch_latest_release(github_repo)
    if not release:
        return False

    if frozen:
        asset = find_exe_asset(release)
        if not asset:
            return False
        new_exe = app_dir / "TOOL_OAP.exe.new"
        download_file(asset["browser_download_url"], new_exe, "Telechargement EXE")
        apply_exe_update(app_dir, new_exe)
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
    return True


def run_update_menu(
    github_repo: str,
    app_dir: Path,
    frozen: bool,
    animate_success,
    animate_error,
    animate_info,
    animate_warning,
    animate_transition,
    safe_input,
) -> None:
    animate_transition("Verification GitHub", 0.4)
    try:
        available, message, release = check_update_info(github_repo)
    except Exception as exc:
        animate_error(f"Erreur GitHub: {exc}")
        return

    if not available:
        animate_info(message)
        return

    animate_warning(message)
    if release:
        notes = (release.get("body") or "").strip()
        if notes:
            print(notes[:500])

    confirm = safe_input("Installer la mise a jour ? (o/n): ")
    if not confirm or confirm.lower() not in {"o", "oui", "y", "yes"}:
        animate_info("Mise a jour annulee.")
        return

    try:
        if install_update(github_repo, app_dir, release, frozen=frozen):
            if not frozen:
                animate_success("Sources mises a jour. Relance le tool.")
        else:
            animate_error("Echec de la mise a jour.")
    except Exception as exc:
        animate_error(f"Erreur: {exc}")


def auto_check_on_start(
    github_repo: str,
    app_dir: Path,
    frozen: bool,
    enabled: bool,
    animate_info,
    animate_warning,
    safe_input,
) -> None:
    if not enabled or not github_repo_configured(github_repo):
        return

    try:
        available, message, release = check_update_info(github_repo)
    except Exception:
        return

    if not available:
        return

    animate_warning(message)
    confirm = safe_input("Mettre a jour maintenant ? (o/n): ")
    if confirm and confirm.lower() in {"o", "oui", "y", "yes"}:
        try:
            install_update(github_repo, app_dir, release, frozen=frozen)
        except Exception:
            pass

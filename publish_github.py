"""Bump version, commit et publie l'EXE sur GitHub Releases."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "version.py"
EXE_PATH = ROOT / "dist" / "TOOL_OAP.exe"
GITHUB_REPO = "devdee162-web/qsddddqsddqsdqsd"


def find_git() -> str | None:
    found = shutil.which("git")
    if found:
        return found
    for candidate in (
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files\Git\cmd\git.exe",
    ):
        if Path(candidate).exists():
            return candidate
    return None


def find_gh() -> str | None:
    found = shutil.which("gh")
    if found:
        return found
    for candidate in (
        r"C:\Program Files\GitHub CLI\gh.exe",
        r"C:\Program Files (x86)\GitHub CLI\gh.exe",
    ):
        if Path(candidate).exists():
            return candidate
    return None


def read_version() -> str:
    content = VERSION_FILE.read_text(encoding="utf-8")
    match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise RuntimeError("VERSION introuvable dans version.py")
    return match.group(1)


def write_version(version: str) -> None:
    content = VERSION_FILE.read_text(encoding="utf-8")
    updated = re.sub(
        r'VERSION\s*=\s*["\'][^"\']+["\']',
        f'VERSION = "{version}"',
        content,
        count=1,
    )
    VERSION_FILE.write_text(updated, encoding="utf-8")


def bump_patch_version() -> str:
    current = read_version()
    parts = [int(x) for x in current.split(".")]
    while len(parts) < 3:
        parts.append(0)
    parts[2] += 1
    new_version = ".".join(str(x) for x in parts)
    write_version(new_version)
    print(f"Version: v{current} -> v{new_version}")
    return new_version


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    print(">", " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip())
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr
        )
    return result


def git_add_safe(git: str) -> None:
    run_cmd([git, "add", "-A"])
    blocked = [
        ".env",
        "_embedded_secrets.py",
        "accounts.json",
        "dist/.env",
        "dist/accounts.json",
        "dist/TOOL_OAP.exe",
    ]
    for path in blocked:
        run_cmd([git, "reset", "HEAD", "--", path], check=False)


def git_commit_and_push(version: str, git: str) -> None:
    git_add_safe(git)

    status = run_cmd([git, "status", "--porcelain"], check=False)
    if (status.stdout or "").strip():
        run_cmd(
            [
                git,
                "-c",
                "user.name=devdee162-web",
                "-c",
                "user.email=devdee162-web@users.noreply.github.com",
                "commit",
                "-m",
                f"release: v{version}",
            ]
        )
    else:
        print("Aucun changement source a committer.")

    branch = (run_cmd([git, "branch", "--show-current"], check=False).stdout or "").strip() or "main"
    push = run_cmd([git, "push", "-u", "origin", branch], check=False)
    if push.returncode != 0:
        print("ERREUR: git push echoue. Verifie la connexion GitHub (gh auth login).")

    tag = f"v{version}"
    run_cmd([git, "tag", "-f", tag], check=False)
    tag_push = run_cmd([git, "push", "-f", "origin", tag], check=False)
    if tag_push.returncode != 0:
        print(f"ERREUR: push du tag {tag} echoue.")


def publish_release(version: str, gh: str) -> None:
    tag = f"v{version}"
    notes = f"Release automatique TOOL OAP v{version}"

    create = run_cmd(
        [
            gh,
            "release",
            "create",
            tag,
            str(EXE_PATH),
            "--repo",
            GITHUB_REPO,
            "--title",
            f"TOOL OAP v{version}",
            "--notes",
            notes,
            "--latest",
        ],
        check=False,
    )

    if create.returncode != 0:
        print("Release existante, upload du nouvel EXE...")
        run_cmd(
            [
                gh,
                "release",
                "upload",
                tag,
                str(EXE_PATH),
                "--repo",
                GITHUB_REPO,
                "--clobber",
            ],
            check=False,
        )


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "publish"

    if action == "bump":
        bump_patch_version()
        return 0

    if not EXE_PATH.exists():
        print(f"ERREUR: {EXE_PATH} introuvable. Compile d'abord l'exe.")
        return 1

    version = read_version()
    print(f"Publication v{version}...")

    git = find_git()
    if not git:
        print("ERREUR: Git non installe.")
        return 1

    if not (ROOT / ".git").exists():
        run_cmd([git, "init"])
        run_cmd([git, "branch", "-M", "main"])
        run_cmd([git, "remote", "add", "origin", f"https://github.com/{GITHUB_REPO}.git"], check=False)

    git_commit_and_push(version, git)

    gh = find_gh()
    if gh:
        publish_release(version, gh)
        print(f"OK: https://github.com/{GITHUB_REPO}/releases/tag/v{version}")
    else:
        print("GitHub CLI (gh) absent.")
        print("Installe-le: https://cli.github.com/")
        print(f"Puis: gh release create v{version} dist/TOOL_OAP.exe --repo {GITHUB_REPO}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

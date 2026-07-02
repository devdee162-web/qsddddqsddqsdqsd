"""Genere _embedded_secrets.py depuis .env pour la compilation EXE."""

from __future__ import annotations

from pathlib import Path


def main() -> None:
    env: dict[str, str] = {}
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            env[key.strip()] = value.strip()

    content = (
        '"""Secrets integres a la compilation - genere par build_exe.bat."""\n\n'
        f'SYNC_VM_PASS = {env.get("SYNC_VM_PASS", "")!r}\n'
        f'SYNC_VM_HOST = {env.get("SYNC_VM_HOST", "")!r}\n'
    )
    Path("_embedded_secrets.py").write_text(content, encoding="utf-8")
    print("OK: _embedded_secrets.py genere")


if __name__ == "__main__":
    main()

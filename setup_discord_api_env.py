"""Cree discord_api.env depuis .env (token + cle API)."""

from __future__ import annotations

from pathlib import Path


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def main() -> int:
    root = Path(__file__).resolve().parent
    env = parse_env(root / ".env")
    token = env.get("DISCORD_TOKEN", "").strip()
    api_key = env.get("DISCORD_API_KEY", "").strip()
    port = env.get("DISCORD_API_PORT", "8780").strip() or "8780"

    if not token or token == "ton_token_bot_ici":
        print("ERREUR: DISCORD_TOKEN manquant dans .env")
        return 1
    if not api_key:
        print("ERREUR: DISCORD_API_KEY manquant dans .env")
        return 1

    target = root / "discord_api.env"
    content = (
        "# Genere automatiquement — ne pas committer sur GitHub\n\n"
        f"DISCORD_TOKEN={token}\n"
        f"DISCORD_API_KEY={api_key}\n"
        "DISCORD_API_HOST=0.0.0.0\n"
        f"DISCORD_API_PORT={port}\n"
    )
    target.write_text(content, encoding="utf-8")
    print(f"OK: {target.name} cree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

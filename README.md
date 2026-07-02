# TOOL OAP

Tool local pour export Discord, creation de dossiers OAP, recherche et sync VM.

## Installation rapide (EXE)

1. Va dans **Releases** sur GitHub
2. Telecharge `TOOL_OAP.exe`
3. Copie `.env` et `accounts.json` a cote de l'exe
4. Lance `lancer.bat`

## Mises a jour automatiques

Configure dans `.env` :

```
GITHUB_REPO=ton-compte/tool-oap
AUTO_UPDATE_ON_START=true
```

Le tool verifie GitHub au demarrage et propose d'installer la derniere version.

Menu **8** : verifier manuellement les mises a jour.

## Publier une mise a jour (GitHub)

```bash
# 1. Modifier version.py (ex: 1.0.1)
# 2. Commit et push
git add .
git commit -m "fix: correction export"
git push origin main

# 3. Tag release (declenche build EXE automatique)
git tag v1.0.1
git push origin v1.0.1
```

Chaque push sur `main` genere aussi une release `latest` (pre-release) avec le nouvel EXE.

## Developpement local

```bash
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy config.example.env .env
py export_discord.py
```

## Compiler l'EXE en local

Double-clique `build_exe.bat`

## Fichiers sensibles

Ne jamais committer `.env`, `accounts.json`, ni les dossiers `dossiers/` et `export_discord/`.

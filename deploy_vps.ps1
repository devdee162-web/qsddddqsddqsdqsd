$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Vps = "root@151.240.100.86"
$Dest = "/opt/tool_oap_api"

Write-Host "=== Envoi API vers VPS ===" -ForegroundColor Cyan
Write-Host "VPS: $Vps"
Write-Host "Dossier: $Dest"
Write-Host ""
Write-Host "Entre le mot de passe root quand demande."
Write-Host ""

ssh $Vps "mkdir -p $Dest"

$files = @(
    "discord_api_server.py",
    "start_discord_api.sh",
    "install_discord_api_linux.sh",
    "discord_api.env.linux.example"
)

foreach ($file in $files) {
    $local = Join-Path $PSScriptRoot $file
    if (-not (Test-Path $local)) {
        throw "Fichier manquant: $file"
    }
    scp $local "${Vps}:${Dest}/"
}

Write-Host ""
Write-Host "OK fichiers envoyes." -ForegroundColor Green
Write-Host ""
Write-Host "Sur le VPS:"
Write-Host "  cd /opt/tool_oap_api"
Write-Host "  cp discord_api.env.linux.example discord_api.env"
Write-Host "  nano discord_api.env"
Write-Host "  chmod +x *.sh"
Write-Host "  ./install_discord_api_linux.sh"

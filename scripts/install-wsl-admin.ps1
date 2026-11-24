# Ejecutar desde una ventana PowerShell abierta como administrador.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Abre PowerShell como administrador y ejecuta de nuevo este script.'
}
winget install --id Microsoft.WSL --exact --source winget --accept-source-agreements --accept-package-agreements
if ($LASTEXITCODE -ne 0) { throw 'La instalación de WSL falló.' }
wsl --install --no-distribution
Write-Host 'Reinicia Windows si se solicita. Después inicia Docker Desktop y ejecuta scripts/start.ps1.'

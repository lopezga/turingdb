$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Instala Docker Desktop con backend WSL2 y vuelve a ejecutar este script. Consulta README.md.'
}
docker info --format '{{.ServerVersion}}'
if ($LASTEXITCODE -ne 0) { throw 'Inicia Docker Desktop antes de continuar.' }
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
if (Select-String -LiteralPath '.env' -Pattern '^NL_PROVIDER=ollama$' -Quiet) {
    docker compose --profile ai up -d --build
} else {
    docker compose up -d --build
}
if ($LASTEXITCODE -ne 0) { throw 'No se pudo iniciar el proyecto.' }
Write-Host 'Aplicación: http://localhost:8000. Sigue README.md para descargar y cargar los datos.'

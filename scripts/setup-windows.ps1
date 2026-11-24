# Entry point for Windows. Does not register startup tasks or automatically reboot.
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$PrerequisitesOnly,
    [ValidateSet('auto', 'full', 'compact')][string]$Profile = 'auto',
    [switch]$MachineOnly,
    [string]$ResultPath
)
$ErrorActionPreference = 'Stop'
$entryScriptPath = $PSCommandPath
. (Join-Path $PSScriptRoot 'setup-functions.ps1')
$projectRoot = Split-Path $PSScriptRoot -Parent
$stateDirectory = Join-Path $projectRoot '.setup'
$statePath = Join-Path $stateDirectory 'windows-state.json'

function Ensure-SetupWinget {
    if (Get-Command winget.exe -ErrorAction SilentlyContinue) { return }
    Write-Host 'Preparando WinGet con el modulo oficial Microsoft.WinGet.Client...'
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Install-PackageProvider -Name NuGet -Scope CurrentUser -Force | Out-Null
    Install-Module -Name Microsoft.WinGet.Client -Repository PSGallery -Scope CurrentUser -Force | Out-Null
    Import-Module Microsoft.WinGet.Client -ErrorAction Stop
    Repair-WinGetPackageManager -Latest | Out-Null
    Refresh-SetupPath
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw 'No se pudo preparar WinGet. IT debe habilitar App Installer/Microsoft Store o instalar WinGet desde Microsoft.'
    }
}

function Install-SetupPackage {
    param([string]$Id, [string[]]$Extra = @(), [ValidateSet('install', 'upgrade')][string]$Action = 'install')
    Write-Host "Instalando $Id desde el catalogo oficial de WinGet..."
    $arguments = @($Action, '--id', $Id, '--exact', '--source', 'winget', '--silent',
        '--accept-source-agreements', '--accept-package-agreements', '--disable-interactivity') + $Extra
    $result = Invoke-SetupNative (Get-Command winget.exe).Source $arguments
    Write-Host $result.Output
    if ($result.ExitCode -eq 3010 -or $result.ExitCode -eq 1641) { return $true }
    if ($result.ExitCode -ne 0) {
        throw "WinGet no pudo instalar $Id (codigo $($result.ExitCode)). Revisa el error anterior; puede requerir autorizacion de IT."
    }
    Refresh-SetupPath
    return $false
}

function Save-SetupState {
    param([string]$Stage, [hashtable]$Facts)
    if (-not (Test-Path -LiteralPath $stateDirectory)) { New-Item -ItemType Directory -Path $stateDirectory | Out-Null }
    [pscustomobject]@{ Stage = $Stage; ComputerName = $Facts.ComputerName; BootUtc = $Facts.BootUtc;
        UpdatedUtc = [DateTime]::UtcNow.ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
}

function Invoke-SetupMachinePhase {
    param([hashtable]$Facts)
    $needs = $Facts.FeatureVmp -ne 'Enabled' -or $Facts.FeatureWsl -ne 'Enabled' -or
        (-not $Facts.WslVersion) -or [version]$Facts.WslVersion -lt [version]'2.1.5' -or $Facts.DockerServiceAutomatic
    if (-not $needs) { return $false }
    Write-Host 'Windows solicitara permisos de administrador para los componentes del sistema.'
    $report = Join-Path $stateDirectory 'windows-machine-result.json'
    if (Test-Path -LiteralPath $report) { Remove-Item -LiteralPath $report }
    $windowsPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $process = Start-Process -FilePath $windowsPowerShell -Verb RunAs -WindowStyle Hidden -Wait -PassThru `
        -ArgumentList @('-NoProfile', '-File', ('"' + $entryScriptPath + '"'), '-MachineOnly', '-ResultPath', ('"' + $report + '"'))
    if (-not (Test-Path -LiteralPath $report)) {
        throw 'La fase de administrador no genero un resultado. Comprueba UAC, permisos o la politica de ejecucion con IT.'
    }
    $result = Get-Content -Raw -LiteralPath $report | ConvertFrom-Json
    if (-not $result.Success) { throw $result.Error }
    if ($process.ExitCode -ne 0 -and $process.ExitCode -ne 3010) { throw 'Fallo la fase de administrador.' }
    return [bool]$result.RebootRequired
}

function Start-SetupDocker {
    param([string]$Docker)
    if (Get-SetupDockerInfo $Docker) { return }
    Write-Host 'Iniciando Docker Desktop. Si solicita configuracion inicial o licencia, completala en su ventana.'
    # The CLI does not enable Windows logon startup.
    $start = Invoke-SetupNative $Docker @('desktop', 'start')
    if ($start.ExitCode -ne 0) {
        $desktop = Join-Path (Split-Path (Split-Path (Split-Path $Docker))) 'Docker Desktop.exe'
        if (-not (Test-Path -LiteralPath $desktop)) { throw 'Abre Docker Desktop manualmente y vuelve a ejecutar install.cmd.' }
        Start-Process -FilePath $desktop -WindowStyle Hidden | Out-Null
    }
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($timer.Elapsed.TotalSeconds -lt 240) {
        if (Get-SetupDockerInfo $Docker) { return }
        Start-Sleep -Seconds 2
    }
    throw 'Docker no responde. Completa su primer arranque/licencia y comprueba que usa WSL2 y contenedores Linux; vuelve a ejecutar install.cmd.'
}

function Ensure-SetupDockerMemory {
    param([string]$Docker, [int]$TargetGiB)
    $info = Get-SetupDockerInfo $Docker
    if ($info.OSType -ne 'linux') { throw 'Selecciona contenedores Linux con backend WSL2 en Docker Desktop y repite el script.' }
    if ([int64]$info.MemTotal -ge 12GB) { return }
    $running = Invoke-SetupNative $Docker @('ps', '-q')
    $distros = Invoke-SetupNative (Get-Command wsl.exe).Source @('--list', '--running', '--quiet')
    $otherDistros = @($distros.Output -split '\r?\n' | ForEach-Object { $_.Trim() } | Where-Object { $_ -and $_ -notmatch '^docker-desktop(?:-data)?$' })
    if ($running.ExitCode -ne 0 -or $distros.ExitCode -ne 0 -or $running.Output.Trim() -or $otherDistros.Count -gt 0) {
        throw 'Docker tiene menos de 12 GiB. Deten tus contenedores y distribuciones WSL antes de repetir: el script no cerrara trabajos ajenos.'
    }
    $path = Join-Path $env:USERPROFILE '.wslconfig'
    $text = if (Test-Path -LiteralPath $path) { Get-Content -Raw -LiteralPath $path } else { '' }
    $updated = Update-SetupWslConfigText -Text $text -MemoryGiB $TargetGiB
    if ((Test-Path -LiteralPath $path) -and -not (Test-Path -LiteralPath ($path + '.graphscope-backup'))) {
        Copy-Item -LiteralPath $path -Destination ($path + '.graphscope-backup')
    }
    Write-Host "Asignando $TargetGiB GiB a WSL2; se conservan las otras opciones y una copia de .wslconfig."
    $stop = Invoke-SetupNative $Docker @('desktop', 'stop')
    if ($stop.ExitCode -ne 0) { throw 'Cierra Docker Desktop y repite para aplicar la memoria WSL de forma segura.' }
    $shutdown = Invoke-SetupNative (Get-Command wsl.exe).Source @('--shutdown')
    if ($shutdown.ExitCode -ne 0) { throw 'No se pudo apagar WSL para aplicar su memoria.' }
    Write-SetupUtf8 -Path $path -Text $updated
    Start-SetupDocker $Docker
    if ([int64](Get-SetupDockerInfo $Docker).MemTotal -lt 12GB) {
        throw 'Docker sigue con menos de 12 GiB. Revisa sus limites o politicas con IT; .wslconfig tiene una copia de respaldo.'
    }
}

function Invoke-SetupMachineOnly {
    $report = [ordered]@{ Success = $false; RebootRequired = $false; Error = $null }
    $exitCode = 1
    $resolved = $null; $allowed = $null
    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'La fase de sistema requiere administrador.' }
        $resolved = [IO.Path]::GetFullPath($ResultPath)
        $allowed = [IO.Path]::GetFullPath($stateDirectory).TrimEnd('\') + '\'
        if (-not $resolved.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetExtension($resolved) -ne '.json') {
            throw 'Ruta de resultado no permitida.'
        }
        foreach ($name in @('VirtualMachinePlatform', 'Microsoft-Windows-Subsystem-Linux')) {
            $feature = Get-WindowsOptionalFeature -Online -FeatureName $name
            if ("$($feature.State)" -eq 'EnablePending') { $report.RebootRequired = $true }
            elseif ("$($feature.State)" -ne 'Enabled') {
                $enabled = Enable-WindowsOptionalFeature -Online -FeatureName $name -All -NoRestart
                if ($enabled.RestartNeeded) { $report.RebootRequired = $true }
            }
        }
        $wsl = Get-SetupWslVersion
        if (-not $report.RebootRequired -and (-not $wsl -or [version]$wsl -lt [version]'2.1.5')) {
            Ensure-SetupWinget
            if (Install-SetupPackage -Id 'Microsoft.WSL') { $report.RebootRequired = $true }
            $wsl = Get-SetupWslVersion
            if (-not $wsl -or [version]$wsl -lt [version]'2.1.5') {
                if (-not $report.RebootRequired) { throw 'WSL no se ha instalado correctamente; revisa el instalador o la politica de empresa.' }
            }
        }
        $service = Get-Service -Name 'com.docker.service' -ErrorAction SilentlyContinue
        if ($service -and "$($service.StartType)" -eq 'Automatic') { Set-Service -Name 'com.docker.service' -StartupType Manual }
        $report.Success = $true
        $exitCode = if ($report.RebootRequired) { 3010 } else { 0 }
    } catch { $report.Error = $_.Exception.Message }
    # Only a validated, project-local result file may be written as administrator.
    if ($resolved -and $allowed -and $resolved.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase) -and [IO.Path]::GetExtension($resolved) -eq '.json') {
        $report | ConvertTo-Json | Set-Content -LiteralPath $resolved -Encoding UTF8
    }
    exit $exitCode
}

try {
    if ($MachineOnly) { Invoke-SetupMachineOnly }
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'create.py'))) { throw 'Copia la carpeta completa: falta create.py.' }
    $facts = Get-SetupFacts $projectRoot
    $plan = Get-SetupPlan $facts
    Write-Host ('Windows build: ' + $facts.Build + '; RAM fisica: ' + [math]::Round($facts.PhysicalMemory / 1GB, 1) + ' GiB; CPU: ' + $facts.CpuCount)
    foreach ($step in $plan.Steps) { Write-Host ('Pendiente: ' + $step) }
    if ($plan.Blockers.Count -gt 0) { throw ($plan.Blockers -join "`n") }
    if ($CheckOnly) {
        Write-Host 'Diagnostico terminado: no se instalaron paquetes, no se cambiaron archivos y no se iniciaron servicios.'
        Write-Host ('Docker en ejecucion: ' + $facts.DockerRunning + '; RAM Docker: ' + [math]::Round($facts.DockerMemory / 1GB, 1) + ' GiB')
        exit 0
    }
    $previousState = if (Test-Path -LiteralPath $statePath) { Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json } else { $null }
    if (Test-SetupRebootRequired $previousState $facts.ComputerName $facts.BootUtc) {
        Write-Host 'El paso anterior requiere reiniciar Windows. Guarda tu trabajo, reinicia y ejecuta install.cmd otra vez.'
        exit 3010
    }
    Save-SetupState -Stage 'prerequisites' -Facts $facts
    Ensure-SetupWinget
    if (Invoke-SetupMachinePhase $facts) {
        Save-SetupState -Stage 'reboot-required' -Facts $facts
        Write-Host 'Windows necesita reiniciar para activar WSL2. No se reiniciara automaticamente. Repite install.cmd despues del reinicio.'
        exit 3010
    }
    $userWsl = Get-SetupWslVersion
    if (-not $userWsl -or [version]$userWsl -lt [version]'2.1.5') {
        throw 'WSL no esta disponible para esta cuenta. IT debe completar su instalacion/registro antes de continuar.'
    }
    $python = Get-SetupPython
    if (-not $python) {
        $restartPython = Install-SetupPackage -Id 'Python.Python.3.12' -Extra @('--scope', 'user')
        if ($restartPython) { Save-SetupState -Stage 'reboot-required' -Facts $facts; exit 3010 }
        $python = Get-SetupPython
        if (-not $python) { throw 'Python no se encuentra despues de instalarlo. Abre una terminal nueva y repite install.cmd.' }
    }
    $docker = Get-SetupDocker
    if (-not $docker) {
        $restartDocker = Install-SetupPackage -Id 'Docker.DockerDesktop' -Extra @('--custom', '--backend=wsl-2')
        Disable-SetupDockerAutostart
        if ($restartDocker) { Save-SetupState -Stage 'reboot-required' -Facts $facts; exit 3010 }
        $docker = Get-SetupDocker
        if (-not $docker) { throw 'Docker Desktop no se encuentra despues de instalarlo. Revisa el resultado de WinGet.' }
        # A machine install may have registered a privileged service; keep it manual.
        $newFacts = Get-SetupFacts $projectRoot
        if ($newFacts.DockerServiceAutomatic) {
            if (Invoke-SetupMachinePhase $newFacts) { Save-SetupState -Stage 'reboot-required' -Facts $facts; exit 3010 }
        }
    }
    Disable-SetupDockerAutostart
    $env:PATH = (Split-Path $docker) + ';' + $env:PATH
    Assert-SetupLocalDocker $docker
    Start-SetupDocker $docker
    $compose = Invoke-SetupNative $docker @('compose', 'version')
    if ($compose.ExitCode -ne 0) {
        $running = Invoke-SetupNative $docker @('ps', '-q')
        if ($running.ExitCode -ne 0 -or $running.Output.Trim()) { throw 'Deten los otros contenedores antes de actualizar Docker Desktop para instalar Compose.' }
        if (Install-SetupPackage -Id 'Docker.DockerDesktop' -Action upgrade -Extra @('--custom', '--backend=wsl-2')) {
            Save-SetupState -Stage 'reboot-required' -Facts $facts; exit 3010
        }
        Disable-SetupDockerAutostart
        Start-SetupDocker $docker
        $compose = Invoke-SetupNative $docker @('compose', 'version')
        if ($compose.ExitCode -ne 0) { throw 'Compose sigue sin estar disponible. Solicita reparar Docker Desktop a IT.' }
    }
    Ensure-SetupDockerMemory -Docker $docker -TargetGiB $plan.WslMemoryGiB
    Disable-SetupDockerAutostart
    # Prevent inherited third-party native argument preferences from changing UTF-8 output.
    $env:PYTHONUTF8 = '1'
    $check = Invoke-SetupNative $python @((Join-Path $projectRoot 'create.py'), '--check', '--profile', $Profile)
    Write-Host $check.Output
    if ($check.ExitCode -ne 0) { throw 'Los requisitos finales de create.py no se cumplen. Revisa el diagnostico anterior.' }
    Save-SetupState -Stage 'prerequisites-ready' -Facts $facts
    if ($PrerequisitesOnly) { Write-Host 'Requisitos preparados. Para instalar los datos, ejecuta install.cmd sin opciones.'; exit 0 }
    Write-Host 'Preparando ambos datasets, verificando las bases y arrancando la demo. Puede tardar varios minutos...'
    Push-Location $projectRoot
    try {
        & $python (Join-Path $projectRoot 'create.py') --profile $Profile
        if ($LASTEXITCODE -ne 0) { throw 'La preparacion del proyecto no termino. Los datos se conservan; corrige el error y repite install.cmd.' }
    } finally { Pop-Location }
    Save-SetupState -Stage 'complete' -Facts $facts
    Disable-SetupDockerAutostart
    Write-Host 'Proyecto preparado. Arranque manual: no se han registrado tareas de inicio ni reinicios automaticos.'
    exit 0
} catch {
    Write-Host ('INSTALACION DETENIDA: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'No se han borrado bases. Si una politica de empresa bloquea la accion, solicita autorizacion a IT y repite el mismo script.'
    exit 1
}

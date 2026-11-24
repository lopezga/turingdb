# Shared, side-effect-free helpers for the Windows bootstrap. Windows PowerShell 5.1+.
Set-StrictMode -Version Latest

function Invoke-SetupNative {
    param([string]$FilePath, [string[]]$Arguments = @())
    $ErrorActionPreference = 'Continue'
    $lines = @(& $FilePath @Arguments 2>&1)
    $code = $LASTEXITCODE
    [pscustomobject]@{ ExitCode = $code; Output = (($lines | ForEach-Object { "$_" }) -join "`n").Replace([string][char]0, '') }
}

function Refresh-SetupPath {
    $env:PATH = [Environment]::GetEnvironmentVariable('PATH', 'Machine') + ';' +
        [Environment]::GetEnvironmentVariable('PATH', 'User') + ';' + $env:PATH
}

function Get-SetupPython {
    $candidates = New-Object System.Collections.Generic.List[string]
    foreach ($name in @('python.exe', 'python3.exe')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command -and $command.Source -notlike '*\Microsoft\WindowsApps\*') { $candidates.Add($command.Source) }
    }
    foreach ($root in @('HKCU:\Software\Python\PythonCore', 'HKLM:\Software\Python\PythonCore')) {
        foreach ($key in @(Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue)) {
            $installKey = Join-Path $key.PSPath 'InstallPath'
            $item = Get-Item -LiteralPath $installKey -ErrorAction SilentlyContinue
            if ($item) {
                $directory = $item.GetValue('')
                if ($directory) { $candidates.Add((Join-Path $directory 'python.exe')) }
            }
        }
    }
    foreach ($version in @('314', '313', '312', '311', '310')) {
        $candidates.Add((Join-Path $env:LOCALAPPDATA "Programs\Python\Python$version\python.exe"))
        $candidates.Add((Join-Path $env:ProgramFiles "Python$version\python.exe"))
    }
    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $r = Invoke-SetupNative $candidate @('-c', 'import sys; print(str(sys.version_info.major)+chr(46)+str(sys.version_info.minor))')
        if ($r.ExitCode -eq 0 -and $r.Output -match '^3\.(\d+)\s*$' -and [int]$Matches[1] -ge 10) { return $candidate }
    }
    return $null
}

function Get-SetupDocker {
    $candidates = @()
    $command = Get-Command docker.exe -ErrorAction SilentlyContinue
    if ($command) { $candidates += $command.Source }
    $candidates += (Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe')
    $candidates += (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe')
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    return $null
}

function Get-SetupWslVersion {
    $wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
    if (-not $wsl) { return $null }
    $result = Invoke-SetupNative $wsl.Source @('--version')
    if ($result.ExitCode -eq 0 -and $result.Output -match '(\d+\.\d+\.\d+(?:\.\d+)?)') { return $Matches[1] }
    return $null
}

function Get-SetupDockerInfo {
    param([string]$Docker)
    if (-not $Docker) { return $null }
    $r = Invoke-SetupNative $Docker @('info', '--format', '{{json .}}')
    if ($r.ExitCode -eq 0) {
        try { return ($r.Output | ConvertFrom-Json) } catch { return $null }
    }
    return $null
}

function Test-SetupLocalDockerEndpoint {
    param([string]$Endpoint)
    return $Endpoint -match '^npipe:/{4}\./pipe/[^/]+$'
}

function Assert-SetupLocalDocker {
    param([string]$Docker)
    if ($env:DOCKER_HOST -and -not (Test-SetupLocalDockerEndpoint $env:DOCKER_HOST)) {
        throw 'DOCKER_HOST apunta fuera de Docker Desktop local. Usa un contexto local antes de instalar esta demo.'
    }
    $context = Invoke-SetupNative $Docker @('context', 'inspect', '--format', '{{json .Endpoints.docker.Host}}')
    if ($context.ExitCode -ne 0) { throw 'No se pudo comprobar el contexto Docker local.' }
    $endpoint = $context.Output | ConvertFrom-Json
    if (-not (Test-SetupLocalDockerEndpoint $endpoint)) {
        throw 'Selecciona el contexto Docker Desktop local (desktop-linux). El instalador no modifica motores remotos.'
    }
}

function Get-SetupFacts {
    param([string]$ProjectRoot)
    if ($ProjectRoot.StartsWith('\\')) { throw 'Copia el proyecto a una unidad local antes de instalarlo; no ejecutes el instalador desde una ruta UNC.' }
    $computer = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
    $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    $cpus = @(Get-CimInstance Win32_Processor -ErrorAction Stop)
    $features = @{}
    foreach ($name in @('VirtualMachinePlatform', 'Microsoft-Windows-Subsystem-Linux')) {
        try {
            $feature = Get-CimInstance Win32_OptionalFeature -Filter "Name='$name'" -ErrorAction Stop
            $features[$name] = if ($feature -and $feature.InstallState -eq 1) { 'Enabled' } else { 'Missing' }
        } catch { $features[$name] = 'Unknown' }
    }
    $docker = Get-SetupDocker
    $info = Get-SetupDockerInfo $docker
    $dockerMemory = if ($info) { [int64]$info.MemTotal } else { 0 }
    $projectDrive = New-Object System.IO.DriveInfo([System.IO.Path]::GetPathRoot($ProjectRoot))
    $systemDrive = New-Object System.IO.DriveInfo($env:SystemDrive)
    $service = Get-Service -Name 'com.docker.service' -ErrorAction SilentlyContinue
    $serviceAuto = $false
    if ($service) { $serviceAuto = "$($service.StartType)" -eq 'Automatic' }
    return @{
        Build = [int]$os.BuildNumber; ProductType = [int]$os.ProductType
        Architecture = [int]$cpus[0].Architecture
        PhysicalMemory = [int64]$computer.TotalPhysicalMemory
        CpuCount = [int]$computer.NumberOfLogicalProcessors
        HypervisorPresent = [bool]$computer.HypervisorPresent
        FirmwareVirtualization = @($cpus | Where-Object { $_.VirtualizationFirmwareEnabled }).Count -gt 0
        ProjectFree = [int64]$projectDrive.AvailableFreeSpace; SystemFree = [int64]$systemDrive.AvailableFreeSpace
        FeatureVmp = $features['VirtualMachinePlatform']; FeatureWsl = $features['Microsoft-Windows-Subsystem-Linux']
        WslVersion = Get-SetupWslVersion; Python = Get-SetupPython; Docker = $docker
        DockerMemory = $dockerMemory; DockerRunning = [bool]$info; DockerServiceAutomatic = $serviceAuto
        Winget = [bool](Get-Command winget.exe -ErrorAction SilentlyContinue)
        BootUtc = $os.LastBootUpTime.ToUniversalTime().ToString('o')
        ComputerName = $env:COMPUTERNAME
    }
}

function Get-SetupPlan {
    param([hashtable]$Facts)
    $blockers = @()
    if ($Facts.ProductType -ne 1) { $blockers += 'Este instalador requiere Windows de escritorio, no Windows Server.' }
    if ($Facts.Architecture -ne 9) { $blockers += 'Este instalador esta validado para Windows x64 (Intel/AMD).' }
    if ($Facts.Build -lt 19045 -or ($Facts.Build -ge 22000 -and $Facts.Build -lt 22631)) {
        $blockers += 'Actualiza Windows: se requiere Windows 10 22H2 o Windows 11 23H2 o posterior, con soporte vigente.'
    }
    if (-not $Facts.HypervisorPresent -and -not $Facts.FirmwareVirtualization) {
        $blockers += 'Activa Intel VT-x/AMD-V en BIOS/UEFI; el script no puede hacerlo. En una VM se necesita virtualizacion anidada.'
    }
    if ($Facts.PhysicalMemory -lt 23GB) { $blockers += 'Para esta instalacion completa con dos datasets se requieren al menos 24 GB de RAM fisica (32 GB recomendados).' }
    if ($Facts.CpuCount -lt 2) { $blockers += 'Se requieren al menos dos procesadores logicos.' }
    if ($Facts.ProjectFree -lt 8GB) { $blockers += 'Libera al menos 8 GiB en la unidad de la carpeta del proyecto.' }
    if ($Facts.SystemFree -lt 25GB) { $blockers += 'Libera al menos 25 GiB en la unidad de Windows para instalar dependencias e imagenes.' }
    $needs = @()
    if (-not $Facts.Winget) { $needs += 'Instalar o reparar WinGet mediante Microsoft.WinGet.Client' }
    if (-not $Facts.Python) { $needs += 'Instalar Python 3.12 para el usuario actual' }
    if ($Facts.FeatureVmp -ne 'Enabled' -or $Facts.FeatureWsl -ne 'Enabled') { $needs += 'Comprobar/activar componentes WSL2 con permisos de administrador' }
    if (-not $Facts.WslVersion -or [version]$Facts.WslVersion -lt [version]'2.1.5') { $needs += 'Instalar/actualizar WSL de Microsoft' }
    if (-not $Facts.Docker) { $needs += 'Instalar Docker Desktop con backend WSL2' }
    if ($Facts.DockerServiceAutomatic) { $needs += 'Cambiar com.docker.service a inicio manual' }
    if (-not $Facts.DockerRunning) { $needs += 'Iniciar Docker Desktop para preparar el proyecto' }
    $targetMemory = [math]::Min(24, [math]::Floor($Facts.PhysicalMemory / 1GB) - 6)
    return [pscustomobject]@{ Blockers = @($blockers); Steps = @($needs); WslMemoryGiB = [int]$targetMemory }
}

function Test-SetupRebootRequired {
    param($State, [string]$ComputerName, [string]$BootUtc)
    if ($null -eq $State -or @($State.PSObject.Properties.Name) -notcontains 'Stage' -or
        @($State.PSObject.Properties.Name) -notcontains 'ComputerName' -or @($State.PSObject.Properties.Name) -notcontains 'BootUtc') { return $false }
    return ($State.Stage -eq 'reboot-required' -and
        $State.ComputerName -eq $ComputerName -and $State.BootUtc -eq $BootUtc)
}

function Update-SetupWslConfigText {
    param([AllowEmptyString()][string]$Text, [int]$MemoryGiB)
    if ($MemoryGiB -lt 12 -or $MemoryGiB -gt 24) { throw 'Asignacion WSL fuera del rango permitido.' }
    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($line in ($Text -split '\r?\n')) { $lines.Add($line) }
    $start = -1; $end = $lines.Count
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^\s*\[wsl2\]\s*(?:[#;].*)?$') {
            if ($start -ge 0) { throw 'Hay secciones [wsl2] duplicadas; revisa .wslconfig manualmente.' }
            $start = $i
        } elseif ($start -ge 0 -and $end -eq $lines.Count -and $lines[$i] -match '^\s*\[') { $end = $i }
    }
    if ($start -lt 0) {
        $lines.Add('[wsl2]'); $lines.Add("memory=$($MemoryGiB)GB")
    } else {
        for ($i = $end - 1; $i -gt $start; $i--) {
            if ($lines[$i] -match '^\s*memory\s*=') { $lines.RemoveAt($i) }
        }
        $lines.Insert($start + 1, "memory=$($MemoryGiB)GB")
    }
    return ($lines -join "`r`n").TrimEnd() + "`r`n"
}

function Get-SetupDockerSettingsJson {
    param([AllowEmptyString()][string]$Text)
    $settings = if ($Text.Trim()) { $Text | ConvertFrom-Json } else { [pscustomobject]@{} }
    $settings | Add-Member -NotePropertyName AutoStart -NotePropertyValue $false -Force
    return ($settings | ConvertTo-Json -Depth 100)
}

function Write-SetupUtf8 {
    param([string]$Path, [string]$Text)
    [IO.File]::WriteAllText($Path, $Text, (New-Object Text.UTF8Encoding($false)))
}

function Disable-SetupDockerAutostart {
    # Called for the current interactive user; never writes into another user's profile.
    $directory = Join-Path $env:APPDATA 'Docker'
    $path = Join-Path $directory 'settings-store.json'
    if (-not (Test-Path -LiteralPath $directory)) { New-Item -ItemType Directory -Path $directory -Force | Out-Null }
    if (Test-Path -LiteralPath $path) {
        $text = Get-Content -Raw -LiteralPath $path
    } else { $text = '' }
    $json = Get-SetupDockerSettingsJson $text
    Write-SetupUtf8 -Path $path -Text $json
    $key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
    if (Get-ItemProperty -LiteralPath $key -Name 'Docker Desktop' -ErrorAction SilentlyContinue) {
        Remove-ItemProperty -LiteralPath $key -Name 'Docker Desktop'
    }
}

# No package installations, registry writes, Docker starts or administrator actions.
$ErrorActionPreference = 'Stop'
. (Join-Path (Split-Path $PSScriptRoot -Parent) 'scripts\setup-functions.ps1')
$testCount = 0
function Assert-SetupTest {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
    $script:testCount++
}
function New-SetupFactsFixture {
    return @{ Build=26200; ProductType=1; Architecture=9; PhysicalMemory=32GB; CpuCount=8;
        HypervisorPresent=$true; FirmwareVirtualization=$false; ProjectFree=50GB; SystemFree=60GB;
        FeatureVmp='Enabled'; FeatureWsl='Enabled'; WslVersion='3.0.5'; Python='python.exe'; Docker='docker.exe';
        DockerMemory=16GB; DockerRunning=$false; DockerServiceAutomatic=$false; Winget=$true }
}

$facts = New-SetupFactsFixture
$plan = Get-SetupPlan $facts
Assert-SetupTest ($plan.Blockers.Count -eq 0) 'An active hypervisor must override masked firmware indicators.'
Assert-SetupTest ($plan.Steps.Count -eq 1) 'A prepared PC only needs Docker to be started.'
Assert-SetupTest ($plan.WslMemoryGiB -eq 24) 'WSL allocation must be capped to preserve host memory.'
Assert-SetupTest (Test-SetupLocalDockerEndpoint 'npipe:////./pipe/dockerDesktopLinuxEngine') 'Local Docker Desktop must be accepted.'
Assert-SetupTest (-not (Test-SetupLocalDockerEndpoint 'ssh://company-server')) 'Remote Docker engines must be rejected.'
Assert-SetupTest (-not (Test-SetupLocalDockerEndpoint 'tcp://10.0.0.1:2376')) 'Remote TCP contexts must not be changed by a local installer.'
$facts.HypervisorPresent = $false
Assert-SetupTest ((Get-SetupPlan $facts).Blockers.Count -eq 1) 'Missing firmware virtualization must block setup.'
$facts = New-SetupFactsFixture
$facts.PhysicalMemory = 16GB
Assert-SetupTest ((Get-SetupPlan $facts).Blockers.Count -eq 1) 'Insufficient RAM must block the full project setup.'
$facts = New-SetupFactsFixture
$facts.Build = 22621
Assert-SetupTest ((Get-SetupPlan $facts).Blockers.Count -eq 1) 'Unsupported Windows build must be rejected.'
$facts = New-SetupFactsFixture
$facts.Python = $null; $facts.Docker = $null; $facts.Winget = $false; $facts.WslVersion = $null
$facts.FeatureWsl = 'Missing'; $facts.FeatureVmp = 'Missing'
$plan = Get-SetupPlan $facts
Assert-SetupTest ($plan.Steps.Count -eq 6) 'A clean machine must list all missing dependencies and startup.'
$facts = New-SetupFactsFixture
$facts.SystemFree = 10GB
Assert-SetupTest ((Get-SetupPlan $facts).Blockers.Count -eq 1) 'Insufficient system disk must block installation.'

$state = [pscustomobject]@{ Stage='reboot-required'; ComputerName='test'; BootUtc='boot1' }
Assert-SetupTest (Test-SetupRebootRequired $state 'test' 'boot1') 'Repeating before reboot must stop.'
Assert-SetupTest (-not (Test-SetupRebootRequired $state 'test' 'boot2')) 'After reboot the same command must be allowed to continue.'
Assert-SetupTest (-not (Test-SetupRebootRequired $state 'other-pc' 'boot1')) 'A copied setup state must not block a different computer.'
Assert-SetupTest (-not (Test-SetupRebootRequired $null 'test' 'boot1')) 'No state must be accepted.'

$text = "# Existing config`r`n[wsl2]`r`nmemory=8GB`r`nprocessors=4`r`n[experimental]`r`nautoMemoryReclaim=gradual`r`n"
$updated = Update-SetupWslConfigText $text 24
Assert-SetupTest ($updated -match 'memory=24GB' -and $updated -match 'processors=4' -and $updated -match 'autoMemoryReclaim=gradual') 'Resource adaptation must preserve unrelated WSL settings.'
Assert-SetupTest ($updated -eq (Update-SetupWslConfigText $updated 24)) 'Resource adaptation must be idempotent.'
Assert-SetupTest ((Update-SetupWslConfigText '' 18) -match '\[wsl2\]\s+memory=18GB') 'A clean profile must get a WSL2 memory section.'
$rejected = $false
try { Update-SetupWslConfigText "[wsl2]`n[wsl2]" 18 | Out-Null } catch { $rejected = $true }
Assert-SetupTest $rejected 'Ambiguous WSL configuration must be rejected rather than rewritten.'
$settings = Get-SetupDockerSettingsJson '{"AutoStart":true,"KeepThis":{"enabled":true}}' | ConvertFrom-Json
Assert-SetupTest (-not $settings.AutoStart -and $settings.KeepThis.enabled) 'Disabling Docker startup must preserve unrelated settings.'
$tempFile = [IO.Path]::GetTempFileName()
try {
    Write-SetupUtf8 -Path $tempFile -Text (Get-SetupDockerSettingsJson '')
    $bytes = [IO.File]::ReadAllBytes($tempFile)
    Assert-SetupTest (-not ($bytes[0] -eq 239 -and $bytes[1] -eq 187)) 'Docker JSON must be UTF-8 without a BOM for strict JSON readers.'
} finally { Remove-Item -LiteralPath $tempFile }

$root = Split-Path $PSScriptRoot -Parent
foreach ($name in @('scripts\setup-functions.ps1', 'scripts\setup-windows.ps1')) {
    $tokens = $null; $parseErrors = $null
    [Management.Automation.Language.Parser]::ParseFile((Join-Path $root $name), [ref]$tokens, [ref]$parseErrors) | Out-Null
    Assert-SetupTest (@($parseErrors).Count -eq 0) "Invalid Windows PowerShell syntax: $name"
}
Write-Host "$testCount Windows setup assertions passed. No system settings changed."

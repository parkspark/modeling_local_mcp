[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Image,
    [string]$Name,
    [int]$Seed = 42,
    [string]$ArtifactRoot,
    [string]$PostprocessPlan,
    [switch]$KeepOllamaLoaded
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$imagePath = (Resolve-Path -LiteralPath $Image).Path

Write-Host '[1/5] Input image validated.' -ForegroundColor Cyan
Write-Host "      $imagePath"

if (-not $Name) {
    $Name = [IO.Path]::GetFileNameWithoutExtension($imagePath)
}
if ($Name -notmatch '^[A-Za-z0-9._-]+$') {
    throw 'Name may contain only letters, numbers, dot, underscore, and hyphen.'
}

if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path $workspace 'artifacts'
}
$artifactRootPath = [IO.Path]::GetFullPath($ArtifactRoot)
$artifactDirectory = Join-Path $artifactRootPath $Name
New-Item -ItemType Directory -Force -Path $artifactDirectory | Out-Null
$glbPath = Join-Path $artifactDirectory "$Name.glb"
$logPath = Join-Path $artifactDirectory ("pixal3d-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

if (-not $KeepOllamaLoaded -and (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host '[2/5] Checking Ollama GPU memory usage...' -ForegroundColor Cyan
    try {
        $loadedModels = (& ollama ps 2>$null | Out-String)
        if ($loadedModels -match [regex]::Escape('qwen3.8:27b-mtp-q4_K_M')) {
            Write-Host '      Stopping the loaded Qwen model to free VRAM.'
            & ollama stop 'qwen3.8:27b-mtp-q4_K_M' 2>$null | Out-Null
        }
        else {
            Write-Host '      Qwen is not loaded; no action is needed.'
        }
    }
    catch {
        Write-Warning "Could not inspect or stop Ollama; continuing with Pixal3D. $($_.Exception.Message)"
    }
}

$wslImage = (wsl -d Ubuntu-24.04 -u park -- wslpath -a ($imagePath -replace '\\', '/')).Trim()
$wslGlb = (wsl -d Ubuntu-24.04 -u park -- wslpath -a ($glbPath -replace '\\', '/')).Trim()
$wslLog = (wsl -d Ubuntu-24.04 -u park -- wslpath -a ($logPath -replace '\\', '/')).Trim()
$windowsScript = (Join-Path $workspace 'scripts\generate_pixal3d.sh') -replace '\\', '/'
$wslScript = (wsl -d Ubuntu-24.04 -u park -- wslpath -a $windowsScript).Trim()

Write-Host '[3/5] Generating the 3D GLB with Pixal3D...' -ForegroundColor Cyan
Write-Host '      This is the longest stage. Model download/loading may make the first run slower.'
Write-Host "      Live log: $logPath"
wsl -d Ubuntu-24.04 -u park -- bash $wslScript $wslImage $wslGlb $Seed $wslLog
$pixalExitCode = $LASTEXITCODE
Get-ChildItem -LiteralPath $artifactDirectory -Filter '_tmp_preprocessed_*.png' -File -ErrorAction SilentlyContinue | Remove-Item -Force
if ($pixalExitCode -ne 0) {
    throw "Pixal3D generation failed with exit code $pixalExitCode"
}

Write-Host '[4/5] Converting GLB to editable BLEND and Unity-compatible FBX...' -ForegroundColor Cyan
$convertArguments = @{
    InputGlb = $glbPath
    OutputBase = (Join-Path $artifactDirectory $Name)
}
if ($PostprocessPlan) {
    $convertArguments.PostprocessPlan = (Resolve-Path -LiteralPath $PostprocessPlan).Path
}
& (Join-Path $workspace 'scripts\convert_model.ps1') @convertArguments
Write-Host '[5/5] Complete.' -ForegroundColor Green
Write-Host "      Output: $artifactDirectory"

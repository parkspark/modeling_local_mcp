[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InputGlb,
    [string]$Name,
    [string]$OutputDirectory,
    [int]$Seed = 12345
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$inputPath = (Resolve-Path -LiteralPath $InputGlb).Path
if (-not $Name) {
    $Name = [IO.Path]::GetFileNameWithoutExtension($inputPath)
}
if ($Name -notmatch '^[A-Za-z0-9_-]+$') {
    throw 'Name may contain only ASCII letters, numbers, underscores, and hyphens.'
}
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path (Split-Path -Parent $inputPath) 'rigged'
}
$outputPath = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

$distro = 'Ubuntu-24.04'
$linuxUser = 'park'
$unirigRoot = '/home/park/local-modeling/UniRig'
$condaInit = '/home/park/miniforge3/etc/profile.d/conda.sh'

function Convert-ToWslPath([string]$Path) {
    $fullPath = [IO.Path]::GetFullPath($Path)
    if ($fullPath -notmatch '^([A-Za-z]):\\(.*)$') {
        throw "Only local Windows drive paths can be converted to WSL: $fullPath"
    }
    $drive = $Matches[1].ToLowerInvariant()
    $relative = $Matches[2].Replace('\', '/')
    return "/mnt/$drive/$relative"
}

function Assert-NoWhitespace([string]$Label, [string]$Value) {
    if ($Value -match '\s') {
        throw "$Label contains whitespace, which the upstream UniRig launcher does not support: $Value"
    }
}

function Invoke-UniRig([string]$Command) {
    $script = "set -e; source $condaInit; conda activate unirig; cd $unirigRoot; " +
        'export WANDB_MODE=disabled; export PYTHONUNBUFFERED=1; ' + $Command
    & wsl -d $distro -u $linuxUser -- bash -lc $script
    if ($LASTEXITCODE -ne 0) {
        throw "UniRig command failed with exit code $LASTEXITCODE"
    }
}

function Assert-FreshFile([string]$Path, [datetime]$StartedAt) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Expected output was not created: $Path"
    }
    $item = Get-Item -LiteralPath $Path
    if ($item.Length -eq 0 -or $item.LastWriteTimeUtc -lt $StartedAt) {
        throw "Expected output was not refreshed: $Path"
    }
}

$environmentCheck = & wsl -d $distro -u $linuxUser -- bash -lc `
    "test -x /home/park/miniforge3/envs/unirig/bin/python && test -f $unirigRoot/src/model/sdpa_mha.py"
if ($LASTEXITCODE -ne 0) {
    throw 'The patched UniRig environment is not installed. See docs/humanoid-autorig-test.md.'
}

$wslInput = Convert-ToWslPath $inputPath
$wslOutput = Convert-ToWslPath $outputPath
Assert-NoWhitespace 'Input path' $wslInput
Assert-NoWhitespace 'Output path' $wslOutput

$skeletonPath = Join-Path $outputPath "${Name}_skeleton.fbx"
$skinPath = Join-Path $outputPath "${Name}_skin.fbx"
$riggedGlbPath = Join-Path $outputPath "${Name}_rigged.glb"
$unityBase = Join-Path $outputPath "${Name}_unity"
$humanoidBlendPath = Join-Path $outputPath "${Name}_humanoid.blend"
$humanoidFbxPath = Join-Path $outputPath "${Name}_humanoid.fbx"
$reportPath = Join-Path $outputPath 'rig_report.json'

$startedAt = [DateTime]::UtcNow.AddSeconds(-2)
Invoke-UniRig "bash launch/inference/generate_skeleton.sh --input $wslInput --output $wslOutput/${Name}_skeleton.fbx --seed $Seed --force_override true"
Assert-FreshFile $skeletonPath $startedAt

$startedAt = [DateTime]::UtcNow.AddSeconds(-2)
Invoke-UniRig "bash launch/inference/generate_skin.sh --input $wslOutput/${Name}_skeleton.fbx --output $wslOutput/${Name}_skin.fbx --seed $Seed"
Assert-FreshFile $skinPath $startedAt

$startedAt = [DateTime]::UtcNow.AddSeconds(-2)
Invoke-UniRig "bash launch/inference/merge.sh --source $wslOutput/${Name}_skin.fbx --target $wslInput --output $wslOutput/${Name}_rigged.glb"
Assert-FreshFile $riggedGlbPath $startedAt

& (Join-Path $PSScriptRoot 'convert_model.ps1') -InputGlb $riggedGlbPath -OutputBase $unityBase
if ($LASTEXITCODE -ne 0) {
    throw "Blender conversion failed with exit code $LASTEXITCODE"
}

$blenderCandidates = @(
    'C:\Users\park\Applications\blender-5.2.0-windows-x64\blender.exe',
    'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
)
$blender = $blenderCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $blender) {
    throw 'Blender executable was not found.'
}

$postprocess = Join-Path $PSScriptRoot 'humanoid_postprocess.py'
& $blender --background --factory-startup --python $postprocess -- `
    --input "$unityBase.blend" `
    --blend $humanoidBlendPath `
    --fbx $humanoidFbxPath `
    --report $reportPath
if ($LASTEXITCODE -ne 0) {
    throw "Humanoid post-processing failed with exit code $LASTEXITCODE"
}

$report = Get-Content -Raw -LiteralPath $reportPath | ConvertFrom-Json
if ($report.status -ne 'PASS') {
    throw "Humanoid validation failed. See $reportPath"
}

Write-Host 'Humanoid auto-rig completed.'
Write-Host "FBX    : $humanoidFbxPath"
Write-Host "BLEND  : $humanoidBlendPath"
Write-Host "REPORT : $reportPath"

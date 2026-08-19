[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InputGlb,
    [string]$OutputBase
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$inputPath = (Resolve-Path -LiteralPath $InputGlb).Path

if (-not $OutputBase) {
    $OutputBase = Join-Path (Split-Path -Parent $inputPath) ([IO.Path]::GetFileNameWithoutExtension($inputPath))
}
$outputBasePath = [IO.Path]::GetFullPath($OutputBase)
$outputDirectory = Split-Path -Parent $outputBasePath
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

$blenderCandidates = @(
    'C:\Users\park\Applications\blender-5.2.0-windows-x64\blender.exe',
    'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
)
$blender = $blenderCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $blender) {
    throw 'Blender executable was not found. Run the environment setup first.'
}

$bridge = Join-Path $workspace 'scripts\blender_bridge.py'
$blendPath = "$outputBasePath.blend"
$fbxPath = "$outputBasePath.fbx"

& $blender --background --factory-startup --python $bridge -- `
    --input $inputPath --blend $blendPath --fbx $fbxPath
if ($LASTEXITCODE -ne 0) {
    throw "Blender conversion failed with exit code $LASTEXITCODE"
}

Write-Host "GLB   : $inputPath"
Write-Host "BLEND : $blendPath"
Write-Host "FBX   : $fbxPath"


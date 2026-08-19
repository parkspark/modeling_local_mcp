[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Video,
    [string]$OutputDirectory,
    [ValidateRange(0.1, 3600.0)]
    [double]$EverySeconds = 2.0
)

$ErrorActionPreference = 'Stop'
$videoPath = (Resolve-Path -LiteralPath $Video).Path
if (-not $OutputDirectory) {
    $workspace = Split-Path -Parent $PSScriptRoot
    $name = [IO.Path]::GetFileNameWithoutExtension($videoPath)
    $OutputDirectory = Join-Path $workspace "inputs\${name}_frames"
}
$outputPath = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

$fps = 1.0 / $EverySeconds
$pattern = Join-Path $outputPath 'frame_%04d.jpg'
ffmpeg -hide_banner -y -i $videoPath -vf "fps=$fps" -q:v 2 $pattern
if ($LASTEXITCODE -ne 0) {
    throw "FFmpeg frame extraction failed with exit code $LASTEXITCODE"
}

Write-Host "Frames saved to: $outputPath"


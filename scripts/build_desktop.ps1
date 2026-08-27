[CmdletBinding()]
param(
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
Push-Location $workspace
try {
    if (-not $SkipInstall) {
        python -m pip install -r (Join-Path $workspace 'requirements-desktop.txt')
        if ($LASTEXITCODE -ne 0) {
            throw "Desktop dependency installation failed with exit code $LASTEXITCODE"
        }
    }

    python -m PyInstaller --noconfirm --clean (Join-Path $workspace 'desktop_app.spec')
    if ($LASTEXITCODE -ne 0) {
        throw "Desktop executable build failed with exit code $LASTEXITCODE"
    }

    $executable = Join-Path $workspace 'dist\Local3DModelingStudio.exe'
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        throw "Build completed without the expected executable: $executable"
    }
    Write-Host "Desktop app build complete: $executable" -ForegroundColor Green
}
finally {
    Pop-Location
}

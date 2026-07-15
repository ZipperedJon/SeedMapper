# Build the standalone single-file SeedMapper.exe with PyInstaller.
# Usage:  .\build_exe.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"

Write-Host "Building SeedMapper.exe ..." -ForegroundColor Cyan
& $py -m PyInstaller --noconfirm --onefile --windowed `
    --name SeedMapper `
    --collect-all cubiomespi `
    --distpath "$root\dist" `
    --workpath "$root\build" `
    --specpath "$root" `
    "$root\main.py"

Write-Host "`nDone. Output: $root\dist\SeedMapper.exe" -ForegroundColor Green

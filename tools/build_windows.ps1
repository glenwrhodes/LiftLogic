# Builds the Windows version of Lift Logic and packs it into a zip.
#
#   pwsh tools/build_windows.ps1
#
# Needs Python with the packages in requirements.txt and PyInstaller.
# Output: dist/LiftLogic-windows.zip, holding a LiftLogic folder with
# LiftLogic.exe and everything it needs. No Python is needed to run it.
#
# Copyright (c) 2026 Tiny Moosh Games Inc.

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

foreach ($old in 'build', 'dist') {
    if (Test-Path $old) { Remove-Item -Recurse -Force $old }
}

# --windowed: no console window opens behind the game.
python -m PyInstaller --noconfirm --clean --windowed --name LiftLogic run_liftlogic.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

if (-not (Test-Path 'dist/LiftLogic/LiftLogic.exe')) { throw 'PyInstaller did not produce dist/LiftLogic/LiftLogic.exe' }
Copy-Item README.md 'dist/LiftLogic/README.md'

$zip = 'dist/LiftLogic-windows.zip'
Compress-Archive -Path 'dist/LiftLogic' -DestinationPath $zip
$size = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host "Built $zip ($size MB)"

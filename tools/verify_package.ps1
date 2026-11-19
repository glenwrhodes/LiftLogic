# Proves the packed zip works on its own.
#
#   pwsh tools/verify_package.ps1 [-Zip dist/LiftLogic-windows.zip]
#
# Unzips it into a new empty folder outside the repo, then runs the packaged
# program from there twice without a window: once in check mode, which must
# exit with code 0, and once recording a few frames, which must come out as
# real PNG files. Any failure, or a run that hangs, ends this script with a
# non-zero exit code.
#
# Copyright (c) 2026 Tiny Moosh Games Inc.

param([string]$Zip = 'dist/LiftLogic-windows.zip')

$ErrorActionPreference = 'Stop'
$Zip = (Resolve-Path $Zip).Path
$folder = Join-Path ([IO.Path]::GetTempPath()) ("liftlogic-verify-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $folder | Out-Null
Write-Host "Unzipping $Zip into $folder"
Expand-Archive -Path $Zip -DestinationPath $folder

$exe = Join-Path $folder 'LiftLogic/LiftLogic.exe'
if (-not (Test-Path $exe)) { throw "The zip does not contain LiftLogic/LiftLogic.exe" }

function Invoke-Packaged([string[]]$Arguments, [int]$TimeoutSeconds = 180) {
    $out = Join-Path $folder 'stdout.txt'
    $err = Join-Path $folder 'stderr.txt'
    Write-Host "Running LiftLogic.exe $($Arguments -join ' ')"
    $process = Start-Process -FilePath $exe -ArgumentList $Arguments -WorkingDirectory $folder `
        -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
    $null = $process.Handle     # keeps the exit code readable after it ends
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        $process.Kill()
        throw "LiftLogic.exe was still running after $TimeoutSeconds seconds (probably showing an error box)"
    }
    $output = (Get-Content $out -Raw -ErrorAction SilentlyContinue) + (Get-Content $err -Raw -ErrorAction SilentlyContinue)
    if ($output) { Write-Host $output.TrimEnd() }
    if ($process.ExitCode -ne 0) { throw "LiftLogic.exe exited with code $($process.ExitCode)" }
    return "$output"
}

# Check mode exits with a non-zero code if anything fails. The packaged program
# has no console, so its printed report may or may not be captured here: when
# it is, it must say OK, and when it is not, the exit code decides.
$output = Invoke-Packaged @('--check')
if ($output -and $output -notmatch 'Lift Logic check OK') { throw 'Check mode did not print "Lift Logic check OK"' }

$null = Invoke-Packaged @('--record', 'frames', '--seconds', '0.2', '--fps', '20')
$frames = @(Get-ChildItem (Join-Path $folder 'frames') -Filter 'frame_*.png' -ErrorAction SilentlyContinue)
if ($frames.Count -ne 4) { throw "Expected 4 recorded frames, found $($frames.Count)" }
$signature = [byte[]](0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A)
foreach ($frame in $frames) {
    $bytes = [IO.File]::ReadAllBytes($frame.FullName)
    if ($bytes.Length -lt 1000 -or (Compare-Object $bytes[0..7] $signature)) { throw "$($frame.Name) is not a PNG image" }
}

Remove-Item -Recurse -Force $folder
Write-Host "Package OK: check mode passed and 4 frames were recorded from the unzipped copy"

#!/usr/bin/env pwsh
# Build Windows executable using PyInstaller

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PackageDir = Join-Path $ProjectRoot "package"
$ResourcesDir = Join-Path $PackageDir "resources\win"
$SpecFile = Join-Path $PSScriptRoot "win.spec"

# Ensure resources directory exists
New-Item -ItemType Directory -Force -Path $ResourcesDir | Out-Null

# Install pyinstaller if not present
if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    pip install pyinstaller
}

# Run PyInstaller
Push-Location $PSScriptRoot
try {
    pyinstaller --clean $SpecFile
    $OutputExe = Join-Path $PSScriptRoot "dist\compress-image.exe"
    if (Test-Path $OutputExe) {
        Copy-Item $OutputExe -Destination $ResourcesDir -Force
        Write-Host "Windows build complete: $ResourcesDir\compress-image.exe"
    } else {
        throw "PyInstaller did not produce expected output"
    }
} finally {
    Pop-Location
}
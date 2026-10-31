$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment..."
    py -3 -m venv .venv
}

Write-Host "Installing PyFFB Studio..."
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -e ".[process]"

Write-Host ""
Write-Host "Installed. Start with: .\run.bat"
Write-Host "No hardware? Use:        .\run.bat --simulate"

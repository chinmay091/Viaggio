# Viaggio backend — local dev helper (Windows)
# Usage: .\dev.ps1 <task>   tasks: check | test | migrate | run | shell | help
#
# Local Windows runs use USE_SQLITE=True (no GDAL/PostGIS here).
# Docker is the real PostGIS environment — see docs/IMPLEMENTATION_TRACKER.md.
param(
    [Parameter(Position = 0)]
    [ValidateSet("check", "test", "migrate", "run", "shell", "help")]
    [string]$Task = "help"
)

$ErrorActionPreference = "Stop"
$backend = Split-Path -Parent $MyInvocation.MyCommand.Path

# Python resolution order: $env:VIAGGIO_PYTHON -> known venv -> PATH
$python = $env:VIAGGIO_PYTHON
if (-not $python) {
    $venvPython = "C:\temp\viaggio-venv\Scripts\python.exe"
    if (Test-Path $venvPython) { $python = $venvPython } else { $python = "python" }
}

Set-Location $backend
$env:USE_SQLITE = "True"

switch ($Task) {
    "check"   { & $python manage.py check }
    "test"    { & $python -m pytest }
    "migrate" { & $python manage.py makemigrations; & $python manage.py migrate }
    "run"     { & $python manage.py runserver 0.0.0.0:8000 }
    "shell"   { & $python manage.py shell }
    "help"    { Write-Output "Tasks: check | test | migrate | run | shell" }
}

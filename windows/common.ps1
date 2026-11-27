# Shared helpers for the double-click scripts. Общие функции для скриптов.
$Root = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
$VenvPythonW = Join-Path $Root '.venv\Scripts\pythonw.exe'
$EnvFile = Join-Path $Root '.env'

function Say([string]$ru, [string]$en, [string]$color = 'Gray') {
    Write-Host $ru -ForegroundColor $color
    Write-Host "  ($en)" -ForegroundColor DarkGray
}

function Assert-Ready {
    if (-not (Test-Path $VenvPython)) {
        Say 'Сначала запустите 1-setup.bat' 'Run 1-setup.bat first' 'Red'
        exit 1
    }
    if (-not (Test-Path $EnvFile)) {
        Say 'Нет файла настроек .env. Запустите 1-setup.bat' 'The .env settings file is missing, run 1-setup.bat' 'Red'
        exit 1
    }
}

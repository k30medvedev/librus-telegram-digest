# Step 1: find Python, install the program's libraries, create the settings file.
param([switch]$NoNotepad)
. (Join-Path $PSScriptRoot 'common.ps1')

function Find-Python {
    foreach ($candidate in @(@('py', '-3'), @('python'), @('python3'))) {
        $exe = $candidate[0]
        $extra = @($candidate | Select-Object -Skip 1)
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        try {
            $ok = & $exe @extra -c "import sys; print(sys.version_info >= (3, 10))" 2>$null
        } catch { continue }
        if ("$ok".Trim() -eq 'True') { return , @($exe) + $extra }
    }
    return $null
}

if (-not (Test-Path $VenvPython)) {
    $python = Find-Python
    if (-not $python) {
        Say 'Python 3.10 или новее не найден.' 'Python 3.10+ was not found.' 'Red'
        Say 'Установите его с https://www.python.org/downloads/ и поставьте галочку "Add python.exe to PATH", затем запустите этот файл снова.' `
            'Install it from python.org, tick "Add python.exe to PATH", then run this file again.'
        exit 1
    }
    Say 'Готовлю окружение...' 'Creating the environment...'
    $exe = $python[0]
    $extra = @($python | Select-Object -Skip 1)
    & $exe @extra -m venv (Join-Path $Root '.venv')
    if (-not (Test-Path $VenvPython)) {
        Say 'Не удалось создать окружение.' 'Could not create the environment.' 'Red'
        exit 1
    }
}

Say 'Устанавливаю библиотеки (1-2 минуты)...' 'Installing libraries (1-2 minutes)...'
& $VenvPython -m pip install --disable-pip-version-check --quiet -r (Join-Path $Root 'requirements.txt')
if ($LASTEXITCODE -ne 0) {
    Say 'Установка не удалась. Проверьте интернет (и антивирус), затем запустите снова.' `
        'Installation failed. Check the internet connection (and antivirus), then run again.' 'Red'
    exit 1
}

if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root '.env.example') $EnvFile
    Say 'Создан файл настроек .env' 'Created the .env settings file' 'Green'
}

Say 'Готово! Заполните настройки в открывшемся Блокноте, сохраните (Ctrl+S) и запустите 2-test.bat' `
    'Done! Fill in the settings in Notepad, save (Ctrl+S), then run 2-test.bat' 'Green'
if (-not $NoNotepad) { Start-Process notepad.exe -ArgumentList "`"$EnvFile`"" }

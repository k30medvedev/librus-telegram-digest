# Preview the digest in Notepad (-DryRun) or send it to Telegram right now.
param([switch]$DryRun, [switch]$NoNotepad)
. (Join-Path $PSScriptRoot 'common.ps1')
Assert-Ready
Set-Location $Root
$env:PYTHONUTF8 = '1'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

if ($DryRun) {
    Say 'Читаю дневник, ничего не отправляю...' 'Reading Librus, nothing is sent...'
    $lines = & $VenvPython -m librus_digest --dry-run
    $code = $LASTEXITCODE
    if ($code -ne 0 -or -not $lines) {
        Say 'Не получилось. Прочитайте сообщение об ошибке выше.' 'Failed. Read the error message above.' 'Red'
        exit 1
    }
    # drop Telegram formatting tags so the preview reads like the real message
    $text = ($lines -join "`r`n") -replace '<[^>]+>', ''
    $text = [Net.WebUtility]::HtmlDecode($text)
    $preview = Join-Path $Root 'preview.txt'
    [IO.File]::WriteAllText($preview, $text, (New-Object Text.UTF8Encoding($true)))
    Say 'Готово: предпросмотр открыт в Блокноте. Если всё верно, запустите 3-send-now.bat' `
        'Done: the preview is open in Notepad. If it looks right, run 3-send-now.bat' 'Green'
    if (-not $NoNotepad) { Start-Process notepad.exe -ArgumentList "`"$preview`"" }
} else {
    Say 'Отправляю сводку в Telegram...' 'Sending the digest to Telegram...'
    & $VenvPython -m librus_digest
    if ($LASTEXITCODE -eq 0) {
        Say 'Отправлено. Проверьте Telegram. Дальше: 4-schedule.bat' 'Sent. Check Telegram. Next: 4-schedule.bat' 'Green'
    } else {
        Say 'Не отправлено. Прочитайте сообщение об ошибке выше.' 'Not sent. Read the error message above.' 'Red'
        exit 1
    }
}

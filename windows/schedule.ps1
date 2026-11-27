# Create (or -Remove) the Windows scheduled task that sends the digest every weekday.
param(
    [string]$Time,
    [string]$TaskName = 'LibrusDigest',
    [switch]$Remove
)
. (Join-Path $PSScriptRoot 'common.ps1')

if ($Remove) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Say 'Расписание удалено.' 'The schedule was removed.' 'Green'
    } else {
        Say 'Расписания нет, удалять нечего.' 'There is no schedule to remove.'
    }
    exit 0
}

Assert-Ready

if (-not $Time) {
    $Time = Read-Host 'Во сколько присылать сводку? Enter = 18:00 / What time? Enter = 18:00'
    if (-not $Time) { $Time = '18:00' }
}
$at = [datetime]::MinValue
if (-not [datetime]::TryParseExact($Time.Trim(), [string[]]@('H:mm', 'HH:mm'),
        [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::None, [ref]$at)) {
    Say "Не понял время '$Time'. Напишите, например, 18:00" "Could not read the time '$Time', use e.g. 18:00" 'Red'
    exit 1
}
$Time = $at.ToString('HH:mm')

$arguments = "-m librus_digest --once-per-day --report-after $Time --log-file librus-digest.log"
$action = New-ScheduledTaskAction -Execute $VenvPythonW -Argument $arguments -WorkingDirectory $Root

# weekdays at the chosen time, retried every 20 minutes until midnight
$weekly = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At $at
$untilMidnight = [timespan]::FromMinutes([math]::Max(21, [math]::Floor(1439 - $at.TimeOfDay.TotalMinutes)))
$weekly.Repetition = (New-ScheduledTaskTrigger -Once -At $at -RepetitionInterval (New-TimeSpan -Minutes 20) `
        -RepetitionDuration $untilMidnight).Repetition

# catch up when you log in, if the computer was off at the scheduled time
$logon = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$logon.Delay = 'PT2M'

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -WakeToRun -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
$description = "Librus -> Telegram digest, weekdays $Time"

try {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $weekly, $logon -Settings $settings `
        -Description $description -Force -ErrorAction Stop | Out-Null
} catch {
    try {
        Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $weekly -Settings $settings `
            -Description $description -Force -ErrorAction Stop | Out-Null
        Say 'Запуск при входе в Windows добавить не удалось, остальное настроено.' `
            'Could not add the at-logon trigger; the rest is set up.' 'Yellow'
    } catch {
        Say "Не удалось создать задачу: $($_.Exception.Message)" 'Could not create the scheduled task.' 'Red'
        exit 1
    }
}

$next = (Get-ScheduledTaskInfo -TaskName $TaskName).NextRunTime
Say "Готово! Сводка будет приходить по будням в $Time. Следующий запуск: $next" `
    "Done! The digest will arrive on weekdays at $Time. Next run: $next" 'Green'
Say 'Компьютер в это время должен быть включён. Не переносите и не удаляйте папку с программой.' `
    'The computer must be on at that time. Do not move or delete the program folder.'

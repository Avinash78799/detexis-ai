$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../tools/local_update.ps1')
$script:calls = [System.Collections.Generic.List[object]]::new()
$script:failBackup = $false
function Invoke-ShieldNative {
    param([string]$Program,[string[]]$Arguments)
    $script:calls.Add(@{Program=$Program;Arguments=$Arguments})
    if ($script:failBackup -and $Arguments[1] -eq 'backup') { throw 'Synthetic backup failure' }
}
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Invoke-ShieldLocalUpdate -ShieldRoot $root -BackupDirectory 'C:\private backup fixture' -Python 'fixture-python.exe'
if ($calls.Count -ne 2 -or $calls[0].Arguments[1] -ne 'backup' -or $calls[1].Arguments[1] -ne 'start' -or $calls[1].Arguments[2] -ne '--local-https') {
    throw 'Backup did not precede local-only startup.'
}
$calls.Clear()
$script:failBackup = $true
$caught = $false
try { Invoke-ShieldLocalUpdate -ShieldRoot $root -BackupDirectory 'C:\private backup fixture' }
catch {
    if ($_.Exception.Message -ne 'Synthetic backup failure') { throw }
    $caught = $true
}
if (-not $caught -or $calls.Count -ne 1 -or $calls[0].Arguments[1] -ne 'backup') { throw 'An update continued after backup failure.' }
Write-Output 'Backup-first order and failure-before-start checks passed; no Docker operations were executed.'
exit 0

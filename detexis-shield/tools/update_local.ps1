param(
    [Parameter(Mandatory=$true)][string]$BackupDirectory,
    [string]$Python = 'python.exe'
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'native_command.ps1')
. (Join-Path $PSScriptRoot 'local_update.ps1')
$shieldRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Invoke-ShieldLocalUpdate -ShieldRoot $shieldRoot -BackupDirectory $BackupDirectory -Python $Python

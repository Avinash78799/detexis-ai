function Invoke-ShieldLocalUpdate {
    param(
        [Parameter(Mandatory=$true)][string]$ShieldRoot,
        [Parameter(Mandatory=$true)][string]$BackupDirectory,
        [string]$Python = 'python.exe'
    )
    $ErrorActionPreference = 'Stop'
    $computerTool = Join-Path $ShieldRoot 'tools/computer.py'
    if (-not (Test-Path -LiteralPath $computerTool -PathType Leaf)) { throw 'Shield computer tool was not found.' }
    # A failed dump/copy must stop the update before image recreation/migration.
    Invoke-ShieldNative -Program $Python -Arguments @($computerTool,'backup','--backup-dir',$BackupDirectory)
    Invoke-ShieldNative -Program $Python -Arguments @($computerTool,'start','--local-https')
    Write-Output 'Local update completed. The backup is local only; browser and sensor checks are still required.'
}

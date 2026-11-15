function Invoke-ShieldNative {
    param(
        [Parameter(Mandatory=$true)][string]$Program,
        [string[]]$Arguments = @()
    )
    $executable = Get-Command $Program -CommandType Application -ErrorAction Stop
    # Windows PowerShell 5.1 wraps native stderr in ErrorRecord objects, even
    # for successful commands. Keep this preference local and check the exit code.
    $ErrorActionPreference = 'Continue'
    $PSNativeCommandUseErrorActionPreference = $false
    & $executable.Source @Arguments 2>&1 | ForEach-Object {
        if ($_ -is [System.Management.Automation.ErrorRecord]) {
            Write-Host $_.ToString()
        } else {
            Write-Output $_
        }
    }
    $nativeExit = $LASTEXITCODE
    if ($nativeExit -ne 0) { throw "$Program failed with exit code $nativeExit." }
}

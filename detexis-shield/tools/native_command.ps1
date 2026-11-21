function Invoke-ShieldNative {
    param(
        [Parameter(Mandatory=$true)][string]$Program,
        [string[]]$Arguments = @()
    )
    # Docker Desktop ships both docker.exe and an extensionless docker file.
    # Resolve the Windows executable explicitly and retain exactly one result.
    if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT -and -not [IO.Path]::GetExtension($Program)) {
        $Program += '.exe'
    }
    $executable = Get-Command $Program -CommandType Application -ErrorAction Stop | Select-Object -First 1
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

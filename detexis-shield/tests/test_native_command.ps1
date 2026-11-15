$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../tools/native_command.ps1')
$fixtureFolder = Join-Path ([IO.Path]::GetTempPath()) ('shield native test ' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixtureFolder | Out-Null
$fixture = Join-Path $fixtureFolder 'fixture.ps1'
try {
    Set-Content -LiteralPath $fixture -Encoding ASCII -Value @'
param([int]$ExitCode, [string]$Value)
[Console]::Error.WriteLine('Synthetic image Pulling progress')
[Console]::Out.WriteLine($Value)
exit $ExitCode
'@
    $arguments = @('-NoProfile','-NonInteractive','-File',$fixture,'-ExitCode','0','-Value','value with spaces')
    $output = @(Invoke-ShieldNative -Program powershell.exe -Arguments $arguments)
    if (($output -join '') -ne 'value with spaces') { throw 'stderr polluted captured stdout or a spaced argument changed.' }
    if ($ErrorActionPreference -ne 'Stop') { throw 'Caller error preference changed.' }
    $failed = $false
    try {
        Invoke-ShieldNative -Program powershell.exe -Arguments @('-NoProfile','-NonInteractive','-File',$fixture,'-ExitCode','7','-Value','failure fixture') | Out-Null
    } catch {
        if ($_.Exception.Message -notmatch 'exit code 7') { throw }
        $failed = $true
    }
    if (-not $failed) { throw 'A failed native command was accepted.' }
    Write-Output 'Native stderr success, nonzero failure, spaced arguments and preference isolation passed.'
} finally {
    Remove-Item -LiteralPath $fixture -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $fixtureFolder -ErrorAction SilentlyContinue
}

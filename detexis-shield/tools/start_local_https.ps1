param(
    [Parameter(Mandatory=$true)]
    [string]$CertificateDirectory
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'native_command.ps1')
$shieldRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$shieldEnvironment = Join-Path $shieldRoot '.computer.env'
if (-not (Test-Path -LiteralPath $shieldEnvironment -PathType Leaf)) {
    throw 'The saved .computer.env is missing. Restore it; do not create replacement database credentials.'
}
$certificateFolder = [IO.Path]::GetFullPath($CertificateDirectory)
New-Item -ItemType Directory -Path $certificateFolder -Force | Out-Null
$certificateFile = Join-Path $certificateFolder ('shield-local-root-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.crt')
if (Test-Path -LiteralPath $certificateFile) { throw 'Certificate export path already exists; retry with a new filename.' }

$shieldCompose = @('compose','-p','detexis-shield-computer','--env-file',$shieldEnvironment)
foreach ($shieldFile in @('docker-compose.yml','docker-compose.computer.yml','docker-compose.malware.yml','docker-compose.local-tls.yml')) {
    $shieldCompose += @('-f',(Join-Path $shieldRoot $shieldFile))
}
$shieldCompose += @('--profile','localtls')

Invoke-ShieldNative -Program docker -Arguments @('info','--format','{{.ServerVersion}}') | Out-Null
try {
    $shieldReady = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/ready' -TimeoutSec 5
    if ($shieldReady.ok -ne $true) { throw 'Unexpected readiness response.' }
} catch { throw 'Shield API is not ready. Restore/start the existing computer instance first.' }
Invoke-ShieldNative -Program docker -Arguments ($shieldCompose + @('config','--quiet'))
Invoke-ShieldNative -Program docker -Arguments ($shieldCompose + @('up','-d','--no-build','--no-deps','localproxy'))
$shieldProxy = ((Invoke-ShieldNative -Program docker -Arguments ($shieldCompose + @('ps','-q','localproxy'))) -join "`n").Trim()
if (-not $shieldProxy) { throw 'Local proxy container was not found.' }
$shieldPort = ((Invoke-ShieldNative -Program docker -Arguments ($shieldCompose + @('port','localproxy','8443'))) -join "`n").Trim()
if ($shieldPort -ne '127.0.0.1:8443') { throw 'Unexpected proxy port mapping. Do not use it until reviewed.' }

# Export only the public CA certificate. No host trust store is modified.
Invoke-ShieldNative -Program docker -Arguments @('cp',"${shieldProxy}:/data/caddy/pki/authorities/local/root.crt",$certificateFile)
$shieldFingerprint = (Get-FileHash -LiteralPath $certificateFile -Algorithm SHA256).Hash
Write-Output ('Public root certificate: ' + $certificateFile)
Write-Output ('File SHA256: ' + $shieldFingerprint)
Write-Output 'Review this certificate before approving any Current User root-trust installation.'
Write-Output 'No Windows/browser trust was installed. Do not bypass certificate warnings or enter credentials yet.'
Write-Output 'Prepared address: https://localhost:8443/app'

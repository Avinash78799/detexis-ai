param(
    [Parameter(Mandatory=$true)]
    [string]$CertificateDirectory
)
$ErrorActionPreference = 'Stop'
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

& docker info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop first.' }
try {
    $shieldReady = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/ready' -TimeoutSec 5
    if ($shieldReady.ok -ne $true) { throw 'Unexpected readiness response.' }
} catch { throw 'Shield API is not ready. Restore/start the existing computer instance first.' }
& docker @shieldCompose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose validation failed; no proxy was started.' }
& docker @shieldCompose up -d --no-build --no-deps localproxy
if ($LASTEXITCODE -ne 0) { throw 'Proxy startup failed. Check port 8443 and the localproxy logs; do not stop unrelated apps.' }
$shieldProxy = (& docker @shieldCompose ps -q localproxy).Trim()
if ($LASTEXITCODE -ne 0 -or -not $shieldProxy) { throw 'Local proxy container was not found.' }
$shieldPort = (& docker @shieldCompose port localproxy 8443).Trim()
if ($LASTEXITCODE -ne 0 -or $shieldPort -ne '127.0.0.1:8443') { throw 'Unexpected proxy port mapping. Do not use it until reviewed.' }

# Export only the public CA certificate. No host trust store is modified.
& docker cp "${shieldProxy}:/data/caddy/pki/authorities/local/root.crt" $certificateFile
if ($LASTEXITCODE -ne 0) { throw 'Public certificate is not ready. Inspect localproxy logs and retry export; never copy a private key.' }
$shieldFingerprint = (Get-FileHash -LiteralPath $certificateFile -Algorithm SHA256).Hash
Write-Output ('Public root certificate: ' + $certificateFile)
Write-Output ('File SHA256: ' + $shieldFingerprint)
Write-Output 'Review this certificate before approving any Current User root-trust installation.'
Write-Output 'No Windows/browser trust was installed. Do not bypass certificate warnings or enter credentials yet.'
Write-Output 'Prepared address: https://localhost:8443/app'

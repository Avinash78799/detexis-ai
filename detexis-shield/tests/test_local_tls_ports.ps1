$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../tools/local_tls_ports.ps1')
Assert-ShieldLocalProxyBindings -Json '{"8443/tcp":[{"HostIp":"127.0.0.1","HostPort":"8443"},{"HostIp":"::1","HostPort":"8443"}]}'
Assert-ShieldLocalProxyBindings -Json '{"8443/tcp":[{"HostIp":"::1","HostPort":"8443"},{"HostIp":"127.0.0.1","HostPort":"8443"}]}'
$bad = @(
    '{"8443/tcp":[{"HostIp":"0.0.0.0","HostPort":"8443"},{"HostIp":"::1","HostPort":"8443"}]}',
    '{"8443/tcp":[{"HostIp":"127.0.0.1","HostPort":"8443"},{"HostIp":"::","HostPort":"8443"}]}',
    '{"8443/tcp":[{"HostIp":"127.0.0.1","HostPort":"8443"}]}',
    '{"8443/tcp":[{"HostIp":"127.0.0.1","HostPort":"8443"},{"HostIp":"::1","HostPort":"443"}]}',
    '{"8443/tcp":[{"HostIp":"127.0.0.1","HostPort":"8443"},{"HostIp":"127.0.0.1","HostPort":"8443"}]}',
    '{"8443/tcp":[{"HostIp":"127.0.0.1","HostPort":"8443"},{"HostIp":"::1","HostPort":"8443"}],"80/tcp":null}'
)
foreach ($item in $bad) {
    $rejected = $false
    try { Assert-ShieldLocalProxyBindings -Json $item } catch { $rejected = $true }
    if (-not $rejected) { throw 'Unsafe or incomplete binding was accepted.' }
}
Write-Output 'Exact IPv4/IPv6 loopback bindings accepted; wildcard, missing, duplicate and unexpected ports rejected.'
exit 0

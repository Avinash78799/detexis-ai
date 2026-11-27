function Assert-ShieldLocalProxyBindings {
    param([Parameter(Mandatory=$true)][string]$Json)
    $bindings = $Json | ConvertFrom-Json
    $properties = @($bindings.PSObject.Properties)
    if ($properties.Count -ne 1 -or $properties[0].Name -ne '8443/tcp') {
        throw 'Unexpected local HTTPS container ports.'
    }
    $ports = @($bindings.'8443/tcp')
    if ($ports.Count -ne 2) { throw 'Expected exactly two loopback HTTPS bindings.' }
    $addresses = @($ports | ForEach-Object {
        if ($_.HostPort -ne '8443') { throw 'Unexpected local HTTPS host port.' }
        $_.HostIp
    })
    if (@($addresses | Where-Object { $_ -eq '127.0.0.1' }).Count -ne 1 -or
        @($addresses | Where-Object { $_ -eq '::1' }).Count -ne 1) {
        throw 'Local HTTPS must bind only IPv4 and IPv6 loopback.'
    }
}

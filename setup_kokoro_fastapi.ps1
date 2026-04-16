param(
    [switch]$CheckEndpoint,
    [switch]$SmokeTest
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$configPath = Join-Path $repoRoot "config.json"
$envPath = Join-Path $repoRoot ".env"
$profileName = "kokoro-fastapi-local"

if (-not (Test-Path $configPath)) {
    throw "Missing config.json at $configPath"
}

$config = Get-Content $configPath -Raw | ConvertFrom-Json
$profile = $config.profiles.$profileName
if (-not $profile) {
    throw "Profile '$profileName' not found in config.json"
}

$endpoint = $profile.tts.http.url
if (-not $endpoint) {
    throw "Profile '$profileName' has no tts.http.url"
}

$envLines = @()
if (Test-Path $envPath) {
    $envLines = Get-Content $envPath
}

$updated = $false
for ($i = 0; $i -lt $envLines.Count; $i++) {
    if ($envLines[$i] -match '^\s*APP_PROFILE\s*=') {
        $envLines[$i] = "APP_PROFILE=$profileName"
        $updated = $true
        break
    }
}

if (-not $updated) {
    $envLines += "APP_PROFILE=$profileName"
}

Set-Content -Path $envPath -Value $envLines -Encoding UTF8

Write-Host "Set APP_PROFILE=$profileName in .env"
Write-Host "Configured endpoint: $endpoint"

$uri = [System.Uri]$endpoint
Write-Host "Run Kokoro container:"
Write-Host "docker run --rm -p $($uri.Port):5000 ghcr.io/remsky/kokoro-fastapi:latest"

if ($CheckEndpoint) {
    $check = Test-NetConnection -ComputerName $uri.Host -Port $uri.Port -WarningAction SilentlyContinue
    if ($check.TcpTestSucceeded) {
        Write-Host "Endpoint port is reachable: $($uri.Host):$($uri.Port)"
    } else {
        Write-Warning "Endpoint port is not reachable yet: $($uri.Host):$($uri.Port)"
    }
}

if ($SmokeTest) {
    $payload = @{
        model = $profile.tts.http.model
        input = "FluxVoice smoke test"
        voice = $profile.tts.http.voice
        response_format = $profile.tts.http.response_format
    } | ConvertTo-Json

    $tempOut = [System.IO.Path]::GetTempFileName()
    try {
        Invoke-WebRequest -Uri $endpoint -Method Post -ContentType "application/json" -Body $payload -OutFile $tempOut | Out-Null
        $size = (Get-Item $tempOut).Length
        if ($size -le 0) {
            throw "Smoke test returned empty audio payload"
        }
        Write-Host "Smoke test passed: received $size bytes of audio from $endpoint"
    } finally {
        if (Test-Path $tempOut) {
            Remove-Item $tempOut -ErrorAction SilentlyContinue
        }
    }
}


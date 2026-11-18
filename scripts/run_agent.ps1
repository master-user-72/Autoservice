param(
    [ValidateSet("app", "tab")]
    [string]$Mode = "app"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$py = Join-Path $root ".venv\Scripts\python.exe"
$pidFile = Join-Path $root "data\server.pid"
$url = "http://127.0.0.1:8080/?launcher=1"

function Find-Browser {
    $roots = @($env:LOCALAPPDATA, $env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ }
    $relPaths = @(
        "Google\Chrome\Application\chrome.exe",
        "Yandex\YandexBrowser\Application\browser.exe",
        "Microsoft\Edge\Application\msedge.exe"
    )

    foreach ($rel in $relPaths) {
        foreach ($rootPath in $roots) {
            $path = Join-Path $rootPath $rel
            if (Test-Path $path) {
                return $path
            }
        }
    }
    return $null
}

function Open-Browser([string]$browserPath, [string]$targetUrl, [string]$launchMode) {
    if ($launchMode -eq "tab") {
        if ($browserPath) {
            Start-Process -FilePath $browserPath -ArgumentList $targetUrl
        } else {
            Start-Process $targetUrl
        }
        return
    }

    if ($browserPath) {
        Start-Process -FilePath $browserPath -ArgumentList "--app=$targetUrl"
    } else {
        Start-Process $targetUrl
    }
}

New-Item -ItemType Directory -Force -Path (Join-Path $root "data") | Out-Null

if (Test-Path $pidFile) {
    $old = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($old) {
        Stop-Process -Id $old -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

$env:AGENT_SHUTDOWN_ON_CLOSE = "1"
$proc = Start-Process -FilePath $py -ArgumentList @(
    "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8080"
) -PassThru -WindowStyle Hidden -WorkingDirectory $root

$proc.Id | Set-Content -Path $pidFile -Encoding ascii

$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        Invoke-WebRequest "http://127.0.0.1:8080/api/health" -UseBasicParsing -TimeoutSec 1 | Out-Null
        $ready = $true
        break
    } catch {
        Start-Sleep -Milliseconds 500
    }
}

if (-not $ready) {
    Write-Host "Server failed to start. Port 8080 may be busy." -ForegroundColor Red
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    exit 1
}

$browser = Find-Browser
if ($browser) {
    Write-Host "Browser: $browser"
} elseif ($Mode -eq "tab") {
    Write-Host "Chrome/Yandex/Edge not found. Opening default browser."
} else {
    Write-Host "Chrome/Yandex/Edge not found. Opening default browser."
}

Open-Browser -browserPath $browser -targetUrl $url -launchMode $Mode

if ($Mode -eq "tab") {
    Write-Host "Close the agent tab to stop the server."
} else {
    Write-Host "Close the agent window to stop the server."
}

try {
    Wait-Process -Id $proc.Id
} catch {
    # Server already stopped.
}

if (Test-Path $pidFile) {
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

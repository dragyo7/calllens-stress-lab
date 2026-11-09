$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
if (-not (Test-Path $chrome)) {
    $chrome = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
}

Write-Host "Using browser: $chrome"
$targetDir = "docs/screenshots"
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}

# Warmup Chrome process
Start-Sleep -Seconds 1
& $chrome --headless=new --disable-gpu --window-size=1440,900 --virtual-time-budget=2000 http://127.0.0.1:8000/#overview 2>$null
Start-Sleep -Seconds 1

$views = @(
    @{ Name = "dashboard_1440x900.png"; Width = 1440; Height = 900; Url = "http://127.0.0.1:8000/" }
)

foreach ($v in $views) {
    $tempFile = Join-Path $env:TEMP "tmp_capture.png"
    if (Test-Path $tempFile) { Remove-Item $tempFile -Force }
    $url = $v.Url
    $w = $v.Width
    $h = $v.Height
    $outPath = Join-Path $targetDir $v.Name

    Write-Host "Capturing $($v.Name) at ${w}x${h} ($url)..."
    Start-Process -FilePath $chrome -ArgumentList "--headless=new", "--disable-gpu", "--window-size=$w,$h", "--virtual-time-budget=4000", "--screenshot=$tempFile", "$url" -Wait -NoNewWindow
    Start-Sleep -Milliseconds 800
    if (Test-Path $tempFile) {
        Copy-Item -Path $tempFile -Destination $outPath -Force
        $len = (Get-Item $outPath).Length
        Write-Host "  Saved $outPath ($len bytes)"
    } else {
        Write-Warning "  Failed to capture $tempFile"
    }
}
Write-Host "Screenshot capture batch completed."

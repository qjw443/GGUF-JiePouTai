#Requires -Version 5.1
<#
  用 360 极速浏览器（360X）打开本项目前端。
  误检不到 360 时回退到 Edge，再回退系统默认浏览器。

  用法：
    .\open-360.ps1                 打开 http://127.0.0.1:8899/index.html
    .\open-360.ps1 -Port 9000
    .\open-360.ps1 -File           直接打开 web\index.html（file:// 模式）
    .\open-360.ps1 -List           只打印检测结果
#>
param(
    [int]$Port = 8899,
    [switch]$File,
    [switch]$List,
    [switch]$NoStartServer
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$WebDir = Join-Path $Root 'web'
$IndexFile = Join-Path $WebDir 'index.html'

$b360 = $null
$cand360 = @()
$cand360 += (Join-Path $env:LOCALAPPDATA '360Chrome\Chrome\Application\360chrome.exe')
$cand360 += (Join-Path $env:LOCALAPPDATA '360ChromeX\Chrome\Application\360chrome.exe')
$cand360 += (Join-Path $env:LOCALAPPDATA '360chrome\Chrome\Application\360chrome.exe')
$cand360 += (Join-Path $env:ProgramFiles '360Chrome\Chrome\Application\360chrome.exe')
$pf86 = ${env:ProgramFiles(x86)}
if ($pf86) {
    $cand360 += (Join-Path $pf86 '360Chrome\Chrome\Application\360chrome.exe')
    $cand360 += (Join-Path $pf86 '360\360Chrome\Chrome\Application\360chrome.exe')
}
foreach ($p in $cand360) {
    if (Test-Path $p) { $b360 = $p; break }
}

$edge = $null
$candEdge = @()
if ($pf86) { $candEdge += (Join-Path $pf86 'Microsoft\Edge\Application\msedge.exe') }
$candEdge += (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe')
foreach ($p in $candEdge) {
    if (Test-Path $p) { $edge = $p; break }
}

if ($List) {
    if ($b360) {
        Write-Host ("360 极速浏览器 : {0}" -f $b360) -ForegroundColor Green
    } else {
        Write-Host '360 极速浏览器 : 未安装  下载：https://browser.360.cn/ee/' -ForegroundColor DarkYellow
    }
    if ($edge) {
        Write-Host ("Edge           : {0}" -f $edge) -ForegroundColor Gray
    } else {
        Write-Host 'Edge           : 未安装' -ForegroundColor DarkYellow
    }
    Write-Host ("前端页面       : {0}" -f $IndexFile) -ForegroundColor Gray
    return
}

$url = ""
if ($File) {
    $url = 'file:///' + ($IndexFile -replace '\\', '/')
} else {
    $url = "http://127.0.0.1:$Port/index.html"
    if (-not $NoStartServer) {
        $alive = $false
        try {
            $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -eq 200) { $alive = $true }
        } catch {
            $alive = $false
        }
        if (-not $alive) {
            $dataFile = Join-Path $WebDir 'data\model.js'
            if (-not (Test-Path $dataFile)) {
                Write-Host '前端数据还没生成，先跑 build_web_data.py …' -ForegroundColor Yellow
                Push-Location $Root
                python build_web_data.py
                Pop-Location
            }
            Write-Host "启动本地服务 127.0.0.1:$Port …" -ForegroundColor Cyan
            $args = @('-m', 'http.server', "$Port", '--bind', '127.0.0.1', '--directory', $WebDir)
            Start-Process -FilePath 'python' -ArgumentList $args -WorkingDirectory $Root -WindowStyle Hidden
            for ($i = 0; $i -lt 40; $i++) {
                Start-Sleep -Milliseconds 250
                try {
                    $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
                    if ($resp.StatusCode -eq 200) { break }
                } catch {
                }
            }
        }
        Write-Host "服务就绪：$url" -ForegroundColor Green
    }
}

$chromeArgs = @('--new-window', $url)
if ($b360) {
    Write-Host "用 360 极速浏览器打开：$b360" -ForegroundColor Cyan
    Start-Process -FilePath $b360 -ArgumentList $chromeArgs
} elseif ($edge) {
    Write-Host '没检测到 360 极速浏览器，回退到 Edge。' -ForegroundColor DarkYellow
    Write-Host '下载 360 极速浏览器：https://browser.360.cn/ee/' -ForegroundColor DarkYellow
    Start-Process -FilePath $edge -ArgumentList $chromeArgs
} else {
    Write-Host '没检测到 360 与 Edge，使用系统默认浏览器。' -ForegroundColor DarkYellow
    Start-Process $url
}

Write-Host ''
Write-Host '360 极速浏览器是 Chromium 内核，网页版全部功能（含 3D 点云、中文词表）都能跑。' -ForegroundColor Gray

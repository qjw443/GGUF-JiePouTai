#Requires -Version 5.1
<#
  GGUF 解剖台 · 一键启动脚本
  ------------------------------------------------------------------
  用法：
    .\start.ps1                      装依赖 -> 校验/下载模型 -> 生成前端数据 -> 起服务 -> 开浏览器
    .\start.ps1 -NoBrowser           只起服务，不弹浏览器
    .\start.ps1 -Port 9000           换端口（默认 8899）
    .\start.ps1 -Model foo.gguf      换模型（相对本目录或绝对路径）
    .\start.ps1 -Rebuild             强制重算前端数据 web/data/model.js
    .\start.ps1 -ForceDownload       强制重新下载默认模型
    .\start.ps1 -Stop                停掉后台静态服务
#>
param(
    [string]$Model = 'qwen2.5-0.5b-instruct-q4_k_m.gguf',
    [int]$Port = 8899,
    [string]$PythonExe = '',
    [switch]$NoBrowser,
    [switch]$Rebuild,
    [switch]$ForceDownload,
    [switch]$Stop
)

$ErrorActionPreference = 'Continue'
# 让 Python 的中文输出在 Windows PowerShell 控制台（GBK 代码页）里也正常显示
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
try { $OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$WebDir = Join-Path $Root 'web'
$DataFile = Join-Path $WebDir 'data\model.js'
$PidFile = Join-Path $Root '.serve.pid'
$DefaultModel = 'qwen2.5-0.5b-instruct-q4_k_m.gguf'
$DefaultUrl = 'https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf'

function Say($msg, $color = 'Gray') { Write-Host $msg -ForegroundColor $color }
function Step($n, $msg) { Write-Host ("[{0}/5] " -f $n) -ForegroundColor DarkCyan -NoNewline; Write-Host $msg -ForegroundColor White }
function Ok($msg) { Write-Host ("     OK  " + $msg) -ForegroundColor Green }

function Test-Modules($py, [string]$expr) {
    & $py -c ("import " + $expr) *> $null
    return ($LASTEXITCODE -eq 0)
}

function Test-Listening([int]$p) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $iar = $c.BeginConnect('127.0.0.1', $p, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne(600)) { $c.Close(); return $false }
        $c.EndConnect($iar); $c.Close(); return $true
    } catch { return $false }
}

function Test-OurServer([int]$p) {
    try {
        $r = Invoke-WebRequest ("http://127.0.0.1:{0}/index.html" -f $p) -UseBasicParsing -TimeoutSec 4
        return ($r.StatusCode -eq 200 -and $r.Content -match 'GGUF')
    } catch { return $false }
}

function Resolve-Python {
    $cands = @()
    foreach ($n in @('python', 'python3', 'py')) {
        $c = Get-Command $n -ErrorAction SilentlyContinue
        if ($c) { $cands += $c.Source }
    }
    $cands += Get-ChildItem "$env:LOCALAPPDATA\Programs\Python" -Filter python.exe -Recurse -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 4 -ExpandProperty FullName
    $cands += (Join-Path $Root '.venv\Scripts\python.exe')
    foreach ($p in ($cands | Where-Object { $_ })) {
        if (-not (Test-Path $p)) { continue }
        try {
            $v = & $p --version 2>&1
            if ($LASTEXITCODE -eq 0 -and "$v" -match 'Python 3\.(\d+)' -and [int]$Matches[1] -ge 8) { return $p }
        } catch { }
    }
    throw '没找到可用的 Python 3.8+，先装一个：https://www.python.org/downloads/'
}

# ---------------------------------------------------------------- Stop
if ($Stop) {
    $killed = 0
    if (Test-Path $PidFile) {
        $sid = 0
        if ([int]::TryParse((Get-Content $PidFile -Raw).Trim(), [ref]$sid)) {
            Stop-Process -Id $sid -Force -ErrorAction SilentlyContinue
            $killed++
        }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
    Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'http\.server' -and $_.CommandLine -match 'gguf-lab|web' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $killed++ }
    Say ("已停止 {0} 个静态服务进程" -f $killed) 'Yellow'
    return
}

# ---------------------------------------------------------------- 0 环境
Say ''
Say '  ============================================'  'DarkCyan'
Say '   GGUF 解剖台 · 模型知识库与架构可视化'         'Cyan'
Say '  ============================================'  'DarkCyan'
Say ''

Step 1 '检查 Python'
if ($PythonExe) {
    if (-not (Test-Path $PythonExe)) { throw ("指定的 Python 不存在：{0}" -f $PythonExe) }
    $Python = (Resolve-Path $PythonExe).Path
} else {
    $Python = Resolve-Python
}
$pyver = (& $Python --version 2>&1) | Out-String
if ($pyver -notmatch 'Python 3\.(\d+)' -or [int]$Matches[1] -lt 8) {
    throw ("{0} 不是 Python 3.8+：{1}" -f $Python, $pyver)
}
Ok ("{0}  ->  {1}" -f $pyver.TrimEnd(), $Python)

Step 2 '检查依赖（numpy 必需，gguf / safetensors 可选）'
if (-not (Test-Modules $Python 'numpy')) {
    Say '     缺少 numpy，正在安装 …' 'Yellow'
    & $Python -m pip install --disable-pip-version-check --quiet numpy *> $null
    if ($LASTEXITCODE -ne 0 -or -not (Test-Modules $Python 'numpy')) {
        throw 'numpy 安装失败，试着手动：python -m pip install numpy'
    }
    Ok 'numpy 安装完成'
} else {
    $nv = (& $Python -c "import numpy;print(numpy.__version__)" 2>&1) | Out-String
    Ok ("numpy {0} 已就绪" -f $nv.Trim())
}
if (Test-Modules $Python 'gguf, safetensors') {
    Ok 'gguf / safetensors 已就绪'
} else {
    Say '     安装可选依赖 gguf + safetensors（命令行工具与交叉验证需要）…' 'Yellow'
    & $Python -m pip install --disable-pip-version-check --quiet gguf safetensors *> $null
    if (Test-Modules $Python 'gguf, safetensors') {
        Ok 'gguf / safetensors 安装完成'
    } else {
        Say '     可选依赖装不上（Python 版本或编译环境），主流程与前端不受影响' 'DarkYellow'
    }
}

Step 3 '校验模型文件'
$ModelPath = $Model
if (-not [System.IO.Path]::IsPathRooted($ModelPath)) { $ModelPath = Join-Path $Root $Model }
if ($ForceDownload -or -not (Test-Path $ModelPath)) {
    if ($Model -ne $DefaultModel) { throw ("找不到模型：{0}" -f $ModelPath) }
    Say '     本地没有模型，开始从 HuggingFace 下载（468 MiB，首次会久一点）…' 'Yellow'
    Say ("     {0}" -f $DefaultUrl) 'DarkGray'
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        & curl.exe -L --fail --retry 3 --progress-bar -o $ModelPath $DefaultUrl
    } else {
        $prev = $ProgressPreference
        $ProgressPreference = 'Continue'
        Invoke-WebRequest -Uri $DefaultUrl -OutFile $ModelPath -UseBasicParsing
        $ProgressPreference = $prev
    }
    if (-not (Test-Path $ModelPath) -or (Get-Item $ModelPath).Length -lt 100MB) {
        throw ("模型下载失败，可手动下载后放到 {0}：{1}" -f $Root, $DefaultUrl)
    }
}
$mSize = [math]::Round((Get-Item $ModelPath).Length / 1MB, 2)
Ok ("{0}  ({1} MiB)" -f (Split-Path $ModelPath -Leaf), $mSize)

Step 4 '生成前端数据 web/data/model.js'
$needBuild = $Rebuild.IsPresent
if (-not $needBuild) {
    if (-not (Test-Path $DataFile)) {
        $needBuild = $true
    } else {
        $dj = (Get-Item $DataFile).LastWriteTime
        $mj = (Get-Item $ModelPath).LastWriteTime
        $sj = (Get-Item (Join-Path $Root 'build_web_data.py')).LastWriteTime
        if ($dj -lt $mj -or $dj -lt $sj) { $needBuild = $true }
    }
}
if ($needBuild) {
    Say '     解析 GGUF -> 反量化 embedding -> PCA -> 近邻索引（约 30~60 秒）…' 'Yellow'
    Push-Location $Root
    try {
        & $Python (Join-Path $Root 'build_web_data.py') $ModelPath
        if ($LASTEXITCODE -ne 0) { throw '前端数据生成失败' }
    } finally { Pop-Location }
    Ok ("model.js 已生成  ({0} MiB)" -f [math]::Round((Get-Item $DataFile).Length / 1MB, 2))
} else {
    Ok ("model.js 已是最新  ({0} MiB)" -f [math]::Round((Get-Item $DataFile).Length / 1MB, 2))
}

Step 5 '启动本地静态服务'
$target = $Port
$reuse = $false
for ($i = 0; $i -lt 25; $i++) {
    if (-not (Test-Listening $target)) { break }
    if (Test-OurServer $target) { $reuse = $true; break }
    $target++
}
if ($target -ge $Port + 25) { throw '附近端口全被占用，用 -Port 指定一个空闲端口' }

if ($reuse) {
    Ok ("{0} 已在运行，直接复用" -f $target)
} else {
    $p = Start-Process -FilePath $Python `
        -ArgumentList @('-m', 'http.server', "$target", '--bind', '127.0.0.1', '--directory', $WebDir) `
        -WorkingDirectory $Root -WindowStyle Hidden -PassThru
    Set-Content -Path $PidFile -Value $p.Id -Encoding ascii
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 250
        if (Test-OurServer $target) { $ready = $true; break }
    }
    if (-not $ready) { throw ("服务启动超时，端口 {0}，日志看 python -m http.server 的窗口" -f $target) }
    Ok ("http://127.0.0.1:{0}/index.html   (PID {1})" -f $target, $p.Id)
}

$url = "http://127.0.0.1:{0}/index.html" -f $target
Say ''
Say '  --------------------------------------------' 'DarkCyan'
Say ("   前端地址   {0}" -f $url) 'White'
Say ("   模型       {0}" -f (Split-Path $ModelPath -Leaf)) 'Gray'
Say ("   参数量     见页面顶部 KPI；视图：概览 / 架构 / 知识库 / 嵌入空间 / 元数据") 'Gray'
Say ("   关闭服务   .\start.ps1 -Stop") 'DarkGray'
Say '  --------------------------------------------' 'DarkCyan'

if (-not $NoBrowser) {
    Start-Process $url
    Say '  已用默认浏览器打开' 'Green'
}
Say ''

#Requires -Version 5.1
<#
  把本项目推送到 GitHub 公开仓库。

  第一次用：
    1) 去 https://github.com/settings/tokens 建一个 token（勾选 repo 权限）
    2) 在当前窗口设置环境变量：
         $env:GITHUB_TOKEN = 'YOUR_GITHUB_TOKEN'
    3) 运行：
         .\push.ps1 -Repo gguf-anatomy

  之后改完代码：
         .\push.ps1                 # 只提交并推送，沿用已配置的 remote

  参数：
    -Repo        仓库名（默认 gguf-anatomy）
    -Owner       GitHub 用户名，不填自动从 token 查询
    -Private     建成私有仓库（默认公开）
    -Message     提交信息
    -Remote      已有远程地址时直接用这个，不新建仓库
#>
param(
    [string]$Repo = 'gguf-anatomy',
    [string]$Owner = '',
    [string]$Token = $env:GITHUB_TOKEN,
    [string]$Description = 'GGUF anatomy workbench: 3D model chain, Chinese vocabulary KB, refusal-direction removal',
    [string]$Message = '',
    [string]$Remote = '',
    [switch]$Private
)

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Git = Join-Path $Root '.tools\git\cmd\git.exe'
if (-not (Test-Path $Git)) {
    $c = Get-Command git -ErrorAction SilentlyContinue
    if ($c) { $Git = $c.Source } else { throw '找不到 git：先跑 .\setup-git.ps1 或安装 Git for Windows' }
}

Push-Location $Root
try {
    if (-not (Test-Path (Join-Path $Root '.git'))) {
        & $Git init -b main | Out-Null
        & $Git config user.name 'GGUF Anatomy'
        & $Git config user.email 'gguf-anatomy@users.noreply.github.com'
    }

    # 提交
    & $Git add -A
    $msg = if ($Message) { $Message } else { '更新：' + (Get-Date -Format 'yyyy-MM-dd HH:mm') }
    & $Git commit -m $msg 2>&1 | Select-Object -Last 2

    if ($Remote) {
        & $Git remote remove origin 2>$null
        & $Git remote add origin $Remote
        & $Git push -u origin main
        return
    }

    if (-not $Token) {
        Write-Host ''
        Write-Host '缺少 GitHub token，仓库已在本地准备好，但无法推送。' -ForegroundColor Yellow
        Write-Host '  1) https://github.com/settings/tokens 建 token（勾 repo）' -ForegroundColor Gray
        Write-Host '  2) $env:GITHUB_TOKEN = ''YOUR_TOKEN''' -ForegroundColor Gray
        Write-Host '  3) 再跑一次 .\push.ps1' -ForegroundColor Gray
        Write-Host ''
        Write-Host '当前提交：' -ForegroundColor Gray
        & $Git log --oneline -1
        return
    }

    $headers = @{ Authorization = "token $Token"; 'User-Agent' = 'gguf-anatomy'; Accept = 'application/vnd.github+json' }
    if (-not $Owner) {
        $me = Invoke-RestMethod -Uri 'https://api.github.com/user' -Headers $headers -TimeoutSec 30
        $Owner = $me.login
    }
    if (-not $Owner) { throw 'token 无效，查不到用户名' }

    $body = @{
        name        = $Repo
        description = $Description
        private     = [bool]$Private
        has_issues  = $true
        has_wiki    = $false
    } | ConvertTo-Json

    try {
        $created = Invoke-RestMethod -Uri 'https://api.github.com/user/repos' -Method Post -Headers $headers `
            -Body ([Text.Encoding]::UTF8.GetBytes($body)) -ContentType 'application/json' -TimeoutSec 40
        Write-Host ("已创建仓库：{0}" -f $created.html_url) -ForegroundColor Green
    } catch {
        Write-Host '仓库已存在或创建失败，继续尝试推送…' -ForegroundColor DarkYellow
    }

    $url = "https://x-access-token:$Token@github.com/$Owner/$Repo.git"
    & $Git remote remove origin 2>$null
    & $Git remote add origin $url
    & $Git push -u origin main
    if ($LASTEXITCODE -eq 0) {
        & $Git remote set-url origin "https://github.com/$Owner/$Repo.git"
        Write-Host ''
        Write-Host ("推送成功：https://github.com/{0}/{1}" -f $Owner, $Repo) -ForegroundColor Green
    } else {
        Write-Host '推送失败：检查 token 权限（需要 repo）与仓库名是否冲突' -ForegroundColor Red
    }
} finally {
    Pop-Location
}

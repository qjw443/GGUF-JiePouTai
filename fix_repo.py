# -*- coding: utf-8 -*-
"""修掉 push protection 拦截：.gitignore 写坏了导致 .gh_token 被提交。重建历史后重新推送。"""
import io
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
GIT = os.path.join(ROOT, '.tools', 'git', 'cmd', 'git.exe')
TOKEN_FILE = os.path.join(ROOT, '.gh_token')
OWNER = 'qjw443'
REPO = 'gguf-anatomy'

GITIGNORE = """# 构建产物
__pycache__/
*.pyc
*.pyo
build/
dist/
*.spec

# 模型权重（体积大，单独下载）
*.gguf
*.safetensors
*.bin
*.pt
*.pth

# 生成的运行数据
web/data/model.js
.serve.pid
.tools/

# 打包的二进制（走 Releases）
*.exe

# 凭据与日志（绝不入库）
.gh_token
gh_upload.log
*.token

# 仓库分发包
*.zip
*.bundle

# 本地测试产物
hf_out/
out/
synthetic.gguf
exp_sim.py
test_*.png

# 系统文件
.DS_Store
Thumbs.db
desktop.ini
"""


def sh(args, cwd=ROOT, check=False):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    if check and p.returncode != 0:
        print('命令失败:', ' '.join(args[:3]), p.stderr[:300])
        sys.exit(1)
    return p


def main():
    # 1) 修正 .gitignore（之前被 PowerShell 写成了 UTF-16）
    with io.open(os.path.join(ROOT, '.gitignore'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(GITIGNORE)
    print('已重写 .gitignore（UTF-8）')

    # 2) 占位符去掉 ghp_ 前缀，避免触发 secret scanning
    repl = [
        ('ghp_xxxxxxxxxxxxxxxx', 'YOUR_GITHUB_TOKEN'),
        ('ghp_xxxxxxxx', 'YOUR_GITHUB_TOKEN'),
        ("'ghp_xxx'", "'YOUR_TOKEN'"),
        ('--token ghp_x', '--token YOUR_TOKEN'),
    ]
    for fn in ('push.ps1', 'README.md', 'README_WEB.md', 'gh_upload.py'):
        p = os.path.join(ROOT, fn)
        if not os.path.exists(p):
            continue
        s = io.open(p, encoding='utf-8').read()
        orig = s
        for a, b in repl:
            s = s.replace(a, b)
        if s != orig:
            io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
            print('已脱敏:', fn)

    # 3) 重建 git 历史（旧历史里含 .gh_token）
    gd = os.path.join(ROOT, '.git')
    if os.path.isdir(gd):
        shutil.rmtree(gd, ignore_errors=True)
        print('已删除旧 .git')

    sh([GIT, 'init', '-b', 'main'], check=True)
    sh([GIT, 'config', 'user.name', 'GGUF Anatomy'], check=True)
    sh([GIT, 'config', 'user.email', 'gguf-anatomy@users.noreply.github.com'], check=True)
    sh([GIT, 'add', '-A'], check=True)

    files = sh([GIT, 'diff', '--cached', '--name-only']).stdout.split()
    bad = [f for f in files if 'gh_token' in f or f.endswith('.gguf') or f.endswith('.exe')]
    if bad:
        print('危险文件仍被暂存:', bad)
        sys.exit(1)
    print('暂存文件 %d 个，无凭据/大文件' % len(files))

    sh([GIT, 'commit', '-m',
        'GGUF 解剖台：桌面版 10 个页面 + 网页版 + 拒答移除 + 三维链路 + 术语词典'], check=True)

    token = io.open(TOKEN_FILE, encoding='utf-8').read().strip() if os.path.exists(TOKEN_FILE) else ''
    if not token:
        print('缺少 .gh_token，先跑 gh_upload.py 授权')
        sys.exit(2)

    url = 'https://x-access-token:%s@github.com/%s/%s.git' % (token, OWNER, REPO)
    sh([GIT, 'remote', 'add', 'origin', url], check=True)
    p = sh([GIT, 'push', '-u', 'origin', 'main'])
    if p.returncode == 0:
        sh([GIT, 'remote', 'set-url', 'origin', 'https://github.com/%s/%s.git' % (OWNER, REPO)])
        print('')
        print('推送成功：https://github.com/%s/%s' % (OWNER, REPO))
    else:
        print('推送失败：')
        print((p.stderr or p.stdout)[:800])


if __name__ == '__main__':
    main()

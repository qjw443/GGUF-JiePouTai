# -*- coding: utf-8 -*-
"""
gh_upload.py —— 用 GitHub Device Flow 拿到 token，自动建公开仓库并推送本项目。

不需要 gh CLI、不需要在本地存密码：
  1. 脚本向 github.com 申请一个 8 位验证码；
  2. 你在浏览器打开 https://github.com/login/device 输入它、点授权；
  3. 脚本轮询到 token 后：创建公开仓库 gguf-anatomy → git push → 打印仓库地址。

用法：
    python gh_upload.py                # 完整流程（等待授权最多 15 分钟）
    python gh_upload.py --repo name    # 换仓库名
    python gh_upload.py --token YOUR_TOKEN  # 已有 token 时直接用
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CLIENT_ID = '178c6fc778ccc68e1d6a'      # GitHub CLI 的公开 client_id，设备流通用
SCOPE = 'public_repo'
ROOT = os.path.dirname(os.path.abspath(__file__))
GIT = os.path.join(ROOT, '.tools', 'git', 'cmd', 'git.exe')
if not os.path.exists(GIT):
    GIT = 'git'
TOKEN_FILE = os.path.join(ROOT, '.gh_token')
LOG = os.path.join(ROOT, 'gh_upload.log')


def log(msg):
    line = time.strftime('[%H:%M:%S] ') + msg
    print(line, flush=True)
    try:
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def http_json(url, data=None, headers=None, method=None):
    h = {'Accept': 'application/json', 'User-Agent': 'gguf-anatomy'}
    if headers:
        h.update(headers)
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def device_login():
    d = http_json('https://github.com/login/device/code',
                  {'client_id': CLIENT_ID, 'scope': SCOPE})
    code = d['user_code']
    uri = d.get('verification_uri', 'https://github.com/login/device')
    log('==============================================')
    log('浏览器打开：' + uri)
    log('输入验证码：' + code)
    log('==============================================')
    interval = max(int(d.get('interval', 5)), 5)
    deadline = time.time() + int(d.get('expires_in', 900))
    while time.time() < deadline:
        time.sleep(interval)
        try:
            t = http_json('https://github.com/login/oauth/access_token', {
                'client_id': CLIENT_ID,
                'device_code': d['device_code'],
                'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
            })
        except Exception as e:
            log('轮询异常（继续）：%s' % e)
            continue
        if 'access_token' in t:
            return t['access_token']
        err = t.get('error')
        if err == 'authorization_pending':
            continue
        if err == 'slow_down':
            interval += 5
            continue
        if err == 'expired_token':
            log('验证码已过期，重新运行本脚本即可')
            return None
        if err == 'access_denied':
            log('授权被拒绝')
            return None
        log('未知返回：%s' % t)
        return None
    return None


def api(method, path, token, payload=None):
    h = {'Authorization': 'token ' + token,
         'Accept': 'application/vnd.github+json',
         'User-Agent': 'gguf-anatomy'}
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request('https://api.github.com' + path, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def run_git(args, cwd=ROOT):
    p = subprocess.run([GIT] + args, cwd=cwd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    if p.returncode != 0:
        log('git %s 失败：%s' % (' '.join(args[:2]), (p.stderr or p.stdout).strip()[:300]))
    return p


def main():
    repo = 'GGUF-JiePouTai'
    token = None
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == '--repo' and i + 1 < len(args):
            repo = args[i + 1]
        if a == '--token' and i + 1 < len(args):
            token = args[i + 1]

    if not token and os.path.exists(TOKEN_FILE):
        token = open(TOKEN_FILE, encoding='utf-8').read().strip()
        log('复用已保存的 token')
    if not token:
        token = device_login()
    if not token:
        log('没有拿到 token，结束')
        sys.exit(2)

    try:
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            f.write(token)
        log('token 已保存到 .gh_token（已加入 .gitignore）')
    except Exception:
        pass

    try:
        me = api('GET', '/user', token)
        owner = me['login']
        log('登录账号：%s' % owner)
    except urllib.error.HTTPError as e:
        log('token 无效：HTTP %s' % e.code)
        sys.exit(3)

    desc = ('GGUF anatomy workbench: 3D model chain, Chinese vocabulary KB, '
            'refusal-direction removal, Windows desktop + web')
    try:
        r = api('POST', '/user/repos', token, {
            'name': repo, 'description': desc, 'private': False,
            'has_issues': True, 'has_wiki': False, 'auto_init': False,
        })
        log('已创建仓库：%s' % r['html_url'])
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')
        if e.code == 422:
            log('仓库已存在，直接推送')
        else:
            log('创建仓库失败 HTTP %s：%s' % (e.code, body[:200]))

    # 提交工作区
    run_git(['add', '-A'])
    run_git(['-c', 'user.name=GGUF Anatomy', '-c', 'user.email=gguf-anatomy@users.noreply.github.com',
             'commit', '-m', '更新：' + time.strftime('%Y-%m-%d %H:%M')])

    url = 'https://x-access-token:%s@github.com/%s/%s.git' % (token, owner, repo)
    run_git(['remote', 'remove', 'origin'])
    run_git(['remote', 'add', 'origin', url])
    p = run_git(['push', '-u', 'origin', 'main'])
    if p.returncode == 0:
        run_git(['remote', 'set-url', 'origin', 'https://github.com/%s/%s.git' % (owner, repo)])
        log('')
        log('推送成功：https://github.com/%s/%s' % (owner, repo))
    else:
        log('推送失败，检查 token 权限（需要 public_repo）')
        sys.exit(4)


if __name__ == '__main__':
    main()

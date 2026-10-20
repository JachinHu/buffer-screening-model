#!/usr/bin/env python3
"""把当前目录推送到 GitHub 并开启 Pages。

用法：
    GITHUB_TOKEN=xxx python scripts/deploy_github.py [repo-name] [--private]

默认创建 Public 仓库（Pages 免费可用）；加 --private 则创建私有仓库。
要求：当前目录已是 git 仓库且有提交；本机 git 可用。
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()


def call(method, path, payload=None, allow_404=False):
    url = path if path.startswith("http") else API + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            body = r.read().decode()
            return r.status, (json.loads(body) if body.strip() else {})
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 404 and allow_404:
            return 404, {}
        try:
            detail = json.loads(body).get("message", body[:200])
        except Exception:
            detail = body[:200]
        raise SystemExit(f"[{method} {path}] {e.code}: {detail}")


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw).stdout.strip()


def main():
    if not TOKEN:
        raise SystemExit("缺少 GITHUB_TOKEN 环境变量")

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    private = "--private" in sys.argv
    repo = args[0] if args else "buffer-screening-model"

    _, me = call("GET", "/user")
    owner = me["login"]
    print(f"账号: {owner}")

    status, _ = call("GET", f"/repos/{owner}/{repo}", allow_404=True)
    if status == 404:
        call("POST", "/user/repos", {
            "name": repo,
            "description": "基于 Panta 8 项检测参数的 buffer 快速筛选模型",
            "private": private,
            "has_issues": True,
            "has_wiki": False,
        })
        print(f"已创建仓库: {owner}/{repo} ({'private' if private else 'public'})")
        time.sleep(2)
    else:
        print(f"仓库已存在: {owner}/{repo}")

    clean = f"https://github.com/{owner}/{repo}.git"
    auth = f"https://x-access-token:{TOKEN}@github.com/{owner}/{repo}.git"
    if "origin" in run(["git", "remote"]).split():
        run(["git", "remote", "set-url", "origin", auth])
    else:
        run(["git", "remote", "add", "origin", auth])
    try:
        run(["git", "push", "-u", "origin", "main"])
    finally:
        # 推送后立刻把 token 从 remote 地址里去掉
        run(["git", "remote", "set-url", "origin", clean])
    print("代码已推送")

    # 开启 Pages（私有仓库需要 Pro；失败不阻断）
    status, _ = call("GET", f"/repos/{owner}/{repo}/pages", allow_404=True)
    if status == 404:
        try:
            call("POST", f"/repos/{owner}/{repo}/pages",
                 {"source": {"branch": "main", "path": "/"}})
            print("Pages 已开启（main / root）")
        except SystemExit as e:
            print(f"Pages 开启失败（私有仓库需 Pro 才能发布站点）: {e}")
            print(f"仓库地址: https://github.com/{owner}/{repo}")
            return
    else:
        print("Pages 已存在，触发重建")
        try:
            call("POST", f"/repos/{owner}/{repo}/pages/builds")
        except SystemExit:
            pass

    url = f"https://{owner}.github.io/{repo}/"
    for _ in range(20):
        _, info = call("GET", f"/repos/{owner}/{repo}/pages")
        if info.get("status") == "built":
            break
        time.sleep(6)
    print(f"站点地址: {url}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""通过 GitHub REST API 提交当前目录（绕过 git push 代理限制）并开启 Pages。

用法：
    GITHUB_TOKEN=xxx python scripts/push_via_api.py [owner/repo]

只在 git 协议不可达时使用；正常情况优先 git push。
"""
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

# 与服务端一致的忽略规则
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules"}
SKIP_SUFFIX = (".pyc", ".log", ".png")
SKIP_PREFIX = ("chk", "sim", "_")


def call(method, path, payload=None, allow=(404,)):
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
        if e.code in allow:
            return e.code, {}
        try:
            detail = json.loads(body).get("message", body[:200])
        except Exception:
            detail = body[:200]
        raise SystemExit(f"[{method} {path}] {e.code}: {detail}")


def collect(root="."):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.startswith(SKIP_PREFIX) and fn != ".gitignore":
                continue
            if fn.endswith(SKIP_SUFFIX):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            files.append((rel, full))
    return sorted(files)


def main():
    if not TOKEN:
        raise SystemExit("缺少 GITHUB_TOKEN 环境变量")

    if len(sys.argv) > 1:
        slug = sys.argv[1]
    else:
        _, me = call("GET", "/user")
        slug = f"{me['login']}/buffer-screening-model"
    print(f"目标仓库: {slug}")

    # 空仓库无法直接使用 Git Data API，先用 contents API 落一个 README 建出首提交
    _, meta = call("GET", f"/repos/{slug}", allow=())
    branch = meta.get("default_branch", "main")
    status, _ = call("GET", f"/repos/{slug}/contents/README.md")
    if status == 404:
        with open("README.md", "rb") as f:
            seed = base64.b64encode(f.read()).decode()
        call("PUT", f"/repos/{slug}/contents/README.md", {
            "message": "初始化仓库", "content": seed, "branch": branch,
        }, allow=())
        print(f"已初始化 {branch} 分支")

    files = collect()
    print(f"待提交文件: {len(files)} 个")

    tree = []
    for rel, full in files:
        with open(full, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        _, blob = call("POST", f"/repos/{slug}/git/blobs",
                       {"content": content, "encoding": "base64"}, allow=())
        tree.append({"path": rel, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    print("blob 上传完成")

    _, new_tree = call("POST", f"/repos/{slug}/git/trees", {"tree": tree}, allow=())

    status, ref = call("GET", f"/repos/{slug}/git/ref/heads/{branch}")
    parents = [ref["object"]["sha"]] if status == 200 else []

    _, commit = call("POST", f"/repos/{slug}/git/commits", {
        "message": "Buffer 快速筛选模型：8 参数权重打分工具与标定数据",
        "tree": new_tree["sha"],
        "parents": parents,
    }, allow=())

    if parents:
        call("PATCH", f"/repos/{slug}/git/refs/heads/{branch}",
             {"sha": commit["sha"]}, allow=())
        print(f"已更新 {branch} 分支")
    else:
        call("POST", f"/repos/{slug}/git/refs",
             {"ref": f"refs/heads/{branch}", "sha": commit["sha"]}, allow=())
        print(f"已创建 {branch} 分支")
    print(f"commit: {commit['sha'][:10]}")

    # 开启 Pages（public 仓库免费）
    status, _ = call("GET", f"/repos/{slug}/pages")
    if status == 404:
        try:
            call("POST", f"/repos/{slug}/pages",
                 {"source": {"branch": branch, "path": "/"}}, allow=())
            print("Pages 已开启")
        except SystemExit as e:
            print(f"Pages 开启失败: {e}")
            return
    else:
        print("Pages 已存在，触发重建")
        try:
            call("POST", f"/repos/{slug}/pages/builds", allow=())
        except SystemExit:
            pass

    owner, repo = slug.split("/")
    for _ in range(25):
        _, info = call("GET", f"/repos/{slug}/pages")
        st = info.get("status")
        if st == "built":
            break
        import time
        time.sleep(6)
    print(f"站点地址: https://{owner}.github.io/{repo}/")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""SessionEnd hook — trigger progress page deploy if HEAD changed.

工作流程：
1. 只在 main 分支生效
2. 读 .towow/progress-deploy-sha（上次成功部署的 SHA）
3. 对比 git rev-parse HEAD
4. 相同 → skip（无改动不必浪费 scp）
5. 不同 → nohup 后台跑 bash scripts/deploy-progress.sh --yes
   （后台 start_new_session 避免阻塞 CC 退出 + CC 退出不会 kill 部署）

硬约束：
- 必须在 SessionEnd hook timeout (10s) 内返回
- 绝不 fail CC 退出（任何异常都 return 0）
- 日志写到 .towow/logs/progress-deploy.log 方便事后排查

触发点：见 .claude/settings.json SessionEnd hooks 数组。
真正的部署脚本：scripts/deploy-progress.sh
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path


def repo_root() -> Path:
    # find-project-root.sh 已经 cd 到仓库根
    return Path.cwd()


def _git(repo: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True, capture_output=True, text=True, timeout=2,
        )
        return result.stdout.strip() or None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def current_head(repo: Path) -> str | None:
    return _git(repo, "rev-parse", "HEAD")


def current_branch(repo: Path) -> str | None:
    return _git(repo, "branch", "--show-current")


def last_deployed_sha(repo: Path) -> str | None:
    sha_file = repo / ".towow" / "progress-deploy-sha"
    if not sha_file.exists():
        return None
    try:
        return sha_file.read_text().strip() or None
    except OSError:
        return None


def log(repo: Path, msg: str) -> None:
    log_dir = repo / ".towow" / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "progress-deploy.log"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with log_file.open("a") as f:
            f.write(f"[{timestamp}] {msg}\n")
    except OSError:
        pass


def main() -> int:
    repo = repo_root()

    # 只在 main 分支生效
    branch = current_branch(repo)
    if branch != "main":
        log(repo, f"skip (branch={branch!r}, not main)")
        return 0

    head = current_head(repo)
    if not head:
        log(repo, "skip (git rev-parse HEAD failed)")
        return 0

    last = last_deployed_sha(repo)
    if last == head:
        log(repo, f"skip (HEAD {head[:8]} already deployed)")
        return 0

    # HEAD changed → trigger async deploy
    script = repo / "scripts" / "deploy-progress.sh"
    if not script.exists():
        log(repo, f"skip (script missing: {script})")
        return 0

    log(repo, f"trigger deploy: HEAD={head[:8]}, last={last[:8] if last else 'none'}")

    # nohup 后台异步跑，不阻塞 CC 退出
    log_file = repo / ".towow" / "logs" / "progress-deploy-run.log"
    try:
        with log_file.open("a") as outf:
            outf.write(f"\n=== {datetime.now().isoformat()} trigger HEAD={head[:8]} ===\n")
            outf.flush()
            subprocess.Popen(
                ["bash", str(script), "--yes"],
                cwd=str(repo),
                stdout=outf,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,  # detach from CC process group
            )
    except OSError as e:
        log(repo, f"Popen failed: {e}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

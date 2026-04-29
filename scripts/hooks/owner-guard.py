#!/usr/bin/env python3
"""
---
name: owner-guard
window_owner: window-0-coordinator
window_owner_since: 2026-04-28T17:00+08:00
window_owner_adr: docs/decisions/ADR-H2-identity-isolation.md
---

PreToolUse hook: window-owner 写屏障
[来源: ADR-042 §D4 + ADR-038 D11 schema-level isolation]

读 docs/handoffs/ownership.yaml，把当前 CC session_id 反查到 window_id，
限制其 Write/Edit 只能写自己 owned_folders + writable_shared_folders。

fail-open：ownership.yaml 缺失 / session_id 未注册 / YAML 解析失败 → allow
（避免锁死仓库；协调员出事会自修复，比误伤好）。

协调员 (role: coordinator) 全仓放行——铺 ADR / 仲裁 / merge 合法跨 owner。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

# ADR-058 §D1 / PLAN-098 WP-07: shared CC PreToolUse helpers. Keeps owner-guard's
# write-barrier output schema-locked at the F-P1-7 contract
# (hookSpecificOutput.permissionDecision), since drift here = silent guard
# bypass on the workspace's most security-sensitive path.
from _hook_output import pre_tool_use_allow, pre_tool_use_deny

CANONICAL_ROOT = Path("/Users/nature/个人项目/Towow")


def _find_main_repo_root(start: Path) -> Path:
    """主 worktree 根（不含 .worktrees/<name>/）。

    依次尝试：
      1. git rev-parse --git-common-dir 的父目录（git-aware，跨 worktree 正确）
      2. legacy walk-up（CLAUDE.md + scripts/guard-feedback.py 双 marker）
      3. CANONICAL_ROOT 兜底

    与 scripts/hooks/find-project-root.sh 语义对齐；inline 实现避免 subprocess 多
    一次 fork 开销（PreToolUse 每次都跑）。guard-20260425-0910 root cause: 原代码
    用 Path.cwd() 当 repo_root，在 worktree 内运行时 cwd = worktree 路径，拼
    `.worktrees/<window>/` 前缀就 double-prefix。
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, cwd=str(start), timeout=2,
        )
        if result.returncode == 0:
            git_common = Path(result.stdout.strip())
            if not git_common.is_absolute():
                git_common = (start / git_common).resolve()
            candidate = git_common.parent
            if (candidate / "CLAUDE.md").is_file() and (candidate / "scripts" / "guard-feedback.py").is_file():
                return candidate
    except (OSError, subprocess.TimeoutExpired):
        pass
    d = start.resolve()
    while d != d.parent:
        if (d / "CLAUDE.md").is_file() and (d / "scripts" / "guard-feedback.py").is_file():
            return d
        d = d.parent
    return CANONICAL_ROOT


def load_windows(repo_root: Path):
    """返回 {session_id: window_dict}；解析失败返回 None（fail-open 信号）。

    Reviewer #2 P1 (Gate 8): 失败必须留 stderr 痕迹，否则 ownership.yaml 写坏
    后写屏障静默失效——这是 5337 schema-drift 的同型故障（"ran, nothing
    reported"）。narrow except 也避免吞掉 KeyboardInterrupt / SystemExit。
    """
    yaml_path = repo_root / "docs" / "handoffs" / "ownership.yaml"
    if not yaml_path.exists():
        return None
    try:
        import yaml
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except ImportError:
        return None
    except (OSError, AttributeError) as exc:
        sys.stderr.write(f"[owner-guard] load_windows IO/attr error: {exc!r}; failing open\n")
        return None
    except Exception as exc:
        sys.stderr.write(f"[owner-guard] load_windows yaml parse error: {exc!r}; failing open\n")
        return None
    out = {}
    for w in (data or {}).get("windows", []) or []:
        sid = w.get("session_id")
        if sid:
            out[sid] = w
    return out


def path_matches(file_abs: Path, folder_rel: str, repo_root: Path) -> bool:
    """file_abs 是否落在 folder_rel 下（folder_rel 可以是文件或目录）。

    macOS APFS 大小写不敏感：dev session PWD case 漂移（lowercase `towow` vs
    canonical `Towow`）会让 Path.resolve() 输出的字符串 case 不一致，普通
    relative_to 字符串比对失败。这里在 string compare 之前用 casefold，确保
    case-insensitive FS 下两种 case 都 match（guard-20260425-0910）。
    """
    if folder_rel.startswith("/"):
        target = Path(folder_rel)
    else:
        target = repo_root / folder_rel
    fr = str(file_abs.resolve()).casefold()
    tr = str(target.resolve()).casefold()
    return fr == tr or fr.startswith(tr + "/")


def main():
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        sys.stderr.write(f"[owner-guard] stdin parse error: {exc!r}; failing open\n")
        pre_tool_use_allow()
        return

    session_id = event.get("session_id") or ""
    tool_input = event.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not file_path or not session_id:
        pre_tool_use_allow()
        return

    repo_root_env = os.environ.get("TOWOW_REPO_ROOT")
    repo_root = Path(repo_root_env) if repo_root_env else _find_main_repo_root(Path.cwd())

    windows = load_windows(repo_root)
    if windows is None:
        pre_tool_use_allow()
        return

    window = windows.get(session_id)
    if window is None:
        pre_tool_use_allow()
        return

    if window.get("role") == "coordinator":
        pre_tool_use_allow()
        return

    file_abs = Path(file_path).expanduser()
    owned = (window.get("owned_folders") or []) + (window.get("writable_shared_folders") or [])
    forbidden = window.get("forbidden_folders") or []

    for f in forbidden:
        if path_matches(file_abs, f, repo_root):
            msg = (
                f"[owner-guard] window {window.get('window_id')} 明确禁止写 {file_path}\n"
                f"forbidden_folders 命中: {f}\n"
                f"处理: 写 SCOPE-OUT 到 docs/decisions/tasks/<window>/LOG.md 并停工，等协调员裁定。"
            )
            pre_tool_use_deny(msg)
            return

    for o in owned:
        if path_matches(file_abs, o, repo_root):
            pre_tool_use_allow()
            return

    msg = (
        f"[owner-guard] window {window.get('window_id')} 写越界: {file_path}\n"
        f"owned_folders + writable_shared_folders 均未命中。\n"
        f"处理: 写 SCOPE-OUT: <path> <reason> 到 docs/decisions/tasks/<window>/LOG.md，"
        f"停工等协调员 adjust ownership.yaml。"
    )
    pre_tool_use_deny(msg)


if __name__ == "__main__":
    main()

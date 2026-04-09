#!/usr/bin/env python3
"""Collect the latest {{PROJECT_NAME}} handoff context from repo and Cloud artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


NOISE_MARKERS = (
    "<local-command-caveat>",
    "<command-name>",
    "<command-message>",
    "<command-args>",
    "<local-command-stdout>",
    "<teammate-message",
    "<task-notification>",
)


@dataclass(frozen=True)
class SessionIntentSummary:
    path: Path
    modified_at: datetime
    messages: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cloud-root",
        default=str(Path.home() / ".claude" / "projects" / "-Users-nature------{{PROJECT_NAME}}"),
        help="Path to the Cloud/Claude project directory",
    )
    parser.add_argument(
        "--recent-sessions",
        type=int,
        default=3,
        help="How many recent transcript sessions to inspect",
    )
    parser.add_argument(
        "--recent-messages",
        type=int,
        default=3,
        help="How many effective user intents to keep per session",
    )
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def fmt_time(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def print_section(title: str) -> None:
    print(f"\n## {title}")


def print_bullet(text: str) -> None:
    print(f"- {text}")


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def truncate_text(text: str, limit: int = 320) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def is_noise_message(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    return any(marker in stripped for marker in NOISE_MARKERS)


def safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def run_git_log(root: Path, limit: int = 8) -> list[str]:
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--date=short",
                f"-n{limit}",
                "--pretty=format:%h %ad %s",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def latest_files(directory: Path, pattern: str, limit: int) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def latest_recursive_files(directory: Path, pattern: str, limit: int) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.rglob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def extract_user_messages(session_path: Path, max_messages: int) -> list[str]:
    messages: list[str] = []
    seen: set[str] = set()
    with session_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if payload.get("type") != "user":
                continue
            message = payload.get("message", {})
            content = message.get("content")
            if not isinstance(content, str):
                continue
            normalized = normalize_text(content)
            if is_noise_message(normalized) or normalized in seen:
                continue
            seen.add(normalized)
            messages.append(truncate_text(normalized))
            if len(messages) >= max_messages:
                break
    return messages


def latest_session_intents(cloud_root: Path, recent_sessions: int, recent_messages: int) -> list[SessionIntentSummary]:
    if not cloud_root.exists():
        return []
    session_paths = sorted(cloud_root.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:recent_sessions]
    summaries: list[SessionIntentSummary] = []
    for session_path in session_paths:
        messages = extract_user_messages(session_path, recent_messages)
        summaries.append(
            SessionIntentSummary(
                path=session_path,
                modified_at=datetime.fromtimestamp(session_path.stat().st_mtime),
                messages=messages,
            )
        )
    return summaries


def print_repo_truth_sources(root: Path) -> None:
    truth_sources = [
        root / "CLAUDE.md",
        root / "MEMORY.md",
        root / "docs" / "INDEX.md",
        root / "backend" / "server.py",
        root / "backend" / "product" / "protocol",
        root / "backend" / "product" / "matching",
        root / "backend" / "product" / "bridge",
        root / "backend" / "product" / "catalyst",
        root / "backend" / "product" / "openagents",
    ]
    print_section("Repo Truth Sources")
    for path in truth_sources:
        if path.exists():
            print_bullet(safe_relative(path, root))


def print_recent_docs(root: Path) -> None:
    print_section("Recent Issue / Decision / Review Candidates")

    issues = latest_files(root / "docs" / "issues", "*.md", limit=4)
    decisions = latest_files(root / "docs" / "decisions", "*.md", limit=6)
    reviews = latest_recursive_files(root / "docs" / "reviews", "*.md", limit=4)

    if issues:
        print_bullet("Issues:")
        for path in issues:
            print(f"  - {safe_relative(path, root)} (mtime {fmt_time(path)})")
    if decisions:
        print_bullet("Decisions:")
        for path in decisions:
            print(f"  - {safe_relative(path, root)} (mtime {fmt_time(path)})")
    if reviews:
        print_bullet("Reviews:")
        for path in reviews:
            print(f"  - {safe_relative(path, root)} (mtime {fmt_time(path)})")


def print_cloud_memory(cloud_root: Path) -> None:
    print_section("Cloud Memory Files")
    memory_dir = cloud_root / "memory"
    if not memory_dir.exists():
        print_bullet(f"Unavailable: {memory_dir}")
        return

    files = latest_files(memory_dir, "*.md", limit=8)
    if not files:
        print_bullet(f"No markdown files found under {memory_dir}")
        return

    for path in files:
        print_bullet(f"{path} (mtime {fmt_time(path)})")


def print_cloud_session_intents(cloud_root: Path, recent_sessions: int, recent_messages: int) -> None:
    print_section("Cloud Transcript Intents")
    if not cloud_root.exists():
        print_bullet(f"Unavailable: {cloud_root}")
        return

    summaries = latest_session_intents(cloud_root, recent_sessions, recent_messages)
    if not summaries:
        print_bullet(f"No transcript sessions found under {cloud_root}")
        return

    for summary in summaries:
        header = f"{summary.path.name} (mtime {summary.modified_at.strftime('%Y-%m-%d %H:%M')})"
        if not summary.messages:
            print_bullet(f"{header} -> no effective user intents found")
            continue
        print_bullet(header)
        for message in summary.messages:
            print(f"  - {message}")


def main() -> int:
    args = parse_args()
    root = repo_root()
    cloud_root = Path(args.cloud_root).expanduser()

    print("# {{PROJECT_NAME}} Dev Handoff Context")
    print_bullet(f"repo_root={root}")
    print_bullet(f"cloud_root={cloud_root}")

    print_repo_truth_sources(root)

    print_section("Recent Git Commits")
    git_lines = run_git_log(root)
    if git_lines:
        for line in git_lines:
            print_bullet(line)
    else:
        print_bullet("Git log unavailable")

    print_recent_docs(root)
    print_cloud_memory(cloud_root)
    print_cloud_session_intents(cloud_root, args.recent_sessions, args.recent_messages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

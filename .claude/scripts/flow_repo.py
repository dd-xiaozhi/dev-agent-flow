#!/usr/bin/env python3
"""
flow_repo.py — Flow Git 仓库操作模块

提供 Flow 仓库的 Git 操作接口：clone、fetch、push、checkout、tags 等。

Usage:
    from flow_repo import FlowRepo
    repo = FlowRepo("https://github.com/xxx/flow.git", Path("/tmp/flow-cache"))
    repo.clone()
    repo.fetch()
    repo.commit_and_push("feat: ...")
"""
from __future__ import annotations
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 默认 Flow 仓库地址
DEFAULT_FLOW_REPO = "https://github.com/dd-xiaozhi/dev-agent-flow.git"

# Flow 仓库本地缓存目录
FLOW_CACHE_DIR = Path.home() / ".cache" / "chatlabs-flow"


@dataclass
class FlowRepo:
    """Flow Git 仓库管理器"""

    repo_url: str = DEFAULT_FLOW_REPO
    local_dir: Optional[Path] = None
    branch: str = "master"

    def __post_init__(self):
        if self.local_dir is None:
            # 从 repo_url 提取仓库名作为目录名
            repo_name = self.repo_url.rstrip("/").split("/")[-1].replace(".git", "")
            self.local_dir = FLOW_CACHE_DIR / repo_name

    @property
    def git_dir(self) -> Path:
        """Git 目录"""
        return self.local_dir / ".git" if self.local_dir else None

    def exists(self) -> bool:
        """检查仓库是否存在且是有效 Git 仓库"""
        if not self.local_dir or not self.local_dir.exists():
            return False
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=str(self.local_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def is_dirty(self) -> bool:
        """检查是否有未提交的变更"""
        if not self.exists():
            return False
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.local_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    def clone(self, branch: Optional[str] = None) -> bool:
        """克隆 Flow 仓库到本地

        Args:
            branch: 要克隆的分支，默认 master

        Returns:
            True if successful
        """
        branch = branch or self.branch
        if self.exists():
            return True  # 已存在，跳过

        self.local_dir.parent.mkdir(parents=True, exist_ok=True)

        try:
            result = subprocess.run(
                ["git", "clone", "--branch", branch, "--single-branch",
                 self.repo_url, str(self.local_dir)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Clone failed: {result.stderr}")
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to clone flow repo: {e}")

    def fetch(self, prune: bool = True) -> bool:
        """从远程获取更新

        Args:
            prune: 是否删除远程已不存在的引用

        Returns:
            True if successful
        """
        if not self.exists():
            return self.clone()

        try:
            cmd = ["git", "fetch", "origin"]
            if prune:
                cmd.append("--prune")
            result = subprocess.run(
                cmd,
                cwd=str(self.local_dir),
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode == 0
        except Exception as e:
            raise RuntimeError(f"Failed to fetch: {e}")

    def pull(self, branch: Optional[str] = None) -> tuple[bool, str]:
        """拉取最新代码

        Args:
            branch: 要拉取的分支

        Returns:
            (success, message)
        """
        branch = branch or self.branch
        if not self.exists():
            return False, "仓库不存在"

        if self.is_dirty():
            return False, "有未提交的变更，请先提交或stash"

        try:
            result = subprocess.run(
                ["git", "pull", "origin", branch],
                cwd=str(self.local_dir),
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                return True, result.stdout.strip() or "拉取成功"
            return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)

    def push(self, message: str, author_name: Optional[str] = None,
             author_email: Optional[str] = None) -> tuple[bool, str, Optional[str]]:
        """提交并推送变更

        Args:
            message: 提交消息
            author_name: 作者名称（可选，使用 git config）
            author_email: 作者邮箱（可选）

        Returns:
            (success, message, commit_hash)
        """
        if not self.exists():
            return False, "仓库不存在", None

        try:
            # 检查是否有变更需要提交
            if not self.is_dirty():
                return False, "没有需要提交的变更", None

            # 添加所有变更
            subprocess.run(
                ["git", "add", "-A"],
                cwd=str(self.local_dir),
                capture_output=True,
                timeout=30,
            )

            # 设置作者（如果提供）
            env = {}
            if author_name:
                env["GIT_AUTHOR_NAME"] = author_name
            if author_email:
                env["GIT_AUTHOR_EMAIL"] = author_email

            # 提交
            commit_result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=str(self.local_dir),
                capture_output=True,
                text=True,
                env={**subprocess.os.environ, **env} if env else None,
                timeout=30,
            )

            if commit_result.returncode != 0:
                return False, f"提交失败: {commit_result.stderr.strip()}", None

            commit_hash = commit_result.stdout.strip().split()[-1] if commit_result.stdout else None

            # 推送
            push_result = subprocess.run(
                ["git", "push", "origin", self.branch],
                cwd=str(self.local_dir),
                capture_output=True,
                text=True,
                timeout=60,
            )

            if push_result.returncode != 0:
                return False, f"提交成功但推送失败: {push_result.stderr.strip()}", commit_hash

            return True, "推送成功", commit_hash

        except Exception as e:
            return False, str(e), None

    def get_current_commit(self, short: bool = True) -> Optional[str]:
        """获取当前 HEAD commit hash"""
        if not self.exists():
            return None

        try:
            flag = "--short" if short else ""
            result = subprocess.run(
                ["git", "rev-parse", flag, "HEAD"],
                cwd=str(self.local_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    def get_remote_commit(self, branch: Optional[str] = None) -> Optional[str]:
        """获取远程最新 commit hash"""
        if not self.exists():
            return None

        branch = branch or self.branch
        try:
            # 先 fetch 确保有最新数据
            self.fetch()

            result = subprocess.run(
                ["git", "rev-parse", "--short", f"origin/{branch}"],
                cwd=str(self.local_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    def get_tags(self) -> list[str]:
        """获取所有版本标签（按时间倒序）"""
        if not self.exists():
            return []

        try:
            result = subprocess.run(
                ["git", "tag", "--sort=-version:refname"],
                cwd=str(self.local_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return [t.strip() for t in result.stdout.strip().split("\n") if t.strip()]
            return []
        except Exception:
            return []

    def checkout(self, ref: str, create_branch: bool = False) -> tuple[bool, str]:
        """切换到指定 commit/tag/branch

        Args:
            ref: commit hash、tag 或 branch 名称
            create_branch: 是否创建新分支

        Returns:
            (success, message)
        """
        if not self.exists():
            return False, "仓库不存在"

        try:
            cmd = ["git", "checkout"]
            if create_branch:
                cmd.extend(["-b", ref])
            else:
                cmd.append(ref)

            result = subprocess.run(
                cmd,
                cwd=str(self.local_dir),
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return True, f"已切换到 {ref}"
            return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)

    def get_log(self, limit: int = 10) -> list[dict]:
        """获取最近提交日志

        Returns:
            [{hash, message, author, date}, ...]
        """
        if not self.exists():
            return []

        try:
            result = subprocess.run(
                ["git", "log", f"--max-count={limit}",
                 "--pretty=format:%H|%s|%an|%ad",
                 "--date=iso"],
                cwd=str(self.local_dir),
                capture_output=True,
                text=True,
                timeout=30,
            )

            logs = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 3)
                if len(parts) >= 4:
                    logs.append({
                        "hash": parts[0][:8],
                        "message": parts[1],
                        "author": parts[2],
                        "date": parts[3],
                    })
            return logs
        except Exception:
            return []

    def get_diff_summary(self) -> list[dict]:
        """获取未提交的变更摘要"""
        if not self.exists() or not self.is_dirty():
            return []

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.local_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )

            changes = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                status = line[:2].strip()
                file_path = line[3:].strip()
                changes.append({
                    "status": status,
                    "file": file_path,
                })
            return changes
        except Exception:
            return []

    def get_current_branch(self) -> Optional[str]:
        """获取当前分支名"""
        if not self.exists():
            return None

        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=str(self.local_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    def stash(self) -> tuple[bool, str]:
        """暂存当前变更"""
        if not self.exists():
            return False, "仓库不存在"

        if not self.is_dirty():
            return True, "没有需要 stash 的变更"

        try:
            result = subprocess.run(
                ["git", "stash", "push", "-m", f"Auto stash {datetime.now().isoformat()}"],
                cwd=str(self.local_dir),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return True, "Stash 成功"
            return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)

    def stash_pop(self) -> tuple[bool, str]:
        """恢复暂存的变更"""
        if not self.exists():
            return False, "仓库不存在"

        try:
            result = subprocess.run(
                ["git", "stash", "pop"],
                cwd=str(self.local_dir),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return True, "Stash pop 成功"
            return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)

    def get_commit_url(self, commit_hash: str) -> str:
        """生成 GitHub commit URL"""
        # 从 repo_url 提取 owner/repo
        parts = self.repo_url.rstrip("/").split("/")
        if len(parts) >= 2:
            repo_path = "/".join(parts[-2:]).replace(".git", "")
            return f"https://github.com/{repo_path}/commit/{commit_hash}"
        return ""

    def read_version(self) -> Optional[str]:
        """从 MANIFEST.md 读取当前 flow 版本"""
        manifest = self.local_dir / ".claude" / "MANIFEST.md"
        if not manifest.exists():
            return None

        try:
            content = manifest.read_text()
            # 支持多种格式:
            # `flow_version: "2.4"` (反引号包裹)
            # flow_version: "2.4"
            # flow_version: 2.4
            import re
            match = re.search(r'flow_version:\s*["\`]*([0-9.]+)["\`]*', content)
            if match:
                return match.group(1)
            return None
        except Exception:
            return None

    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            "repo_url": self.repo_url,
            "local_dir": str(self.local_dir),
            "branch": self.branch,
            "exists": self.exists(),
            "is_dirty": self.is_dirty(),
            "current_commit": self.get_current_commit(),
            "current_branch": self.get_current_branch(),
            "version": self.read_version(),
        }

    def ensure_local(self) -> bool:
        """确保仓库本地存在，不存在则克隆"""
        if not self.exists():
            return self.clone()
        return True


def get_default_flow_repo() -> FlowRepo:
    """获取默认 Flow 仓库实例"""
    return FlowRepo(repo_url=DEFAULT_FLOW_REPO)


def ensure_flow_repo_local() -> FlowRepo:
    """确保 Flow 仓库本地存在，返回仓库实例"""
    repo = get_default_flow_repo()
    if not repo.exists():
        repo.clone()
    return repo

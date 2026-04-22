"""
worktree-manager.py — Git Worktree 状态管理

提供统一的 worktree 创建、查询、合并、清理接口。
每个 story 在独立 worktree 中并行开发，完成后合并回 master。

Usage:
    from worktree_manager import WorktreeManager
    wm = WorktreeManager()
    wm.create_worktree("STORY-001", "新增用户反馈功能")
    wm.list_worktrees()
    wm.merge_to_master("STORY-001")
"""
import json
import os
import subprocess
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_DIR, CHATLABS_DIR


# ── Worktree Root (.worktrees/) ────────────────────────────────────
WORKTREES_ROOT = PROJECT_DIR / ".worktrees"
WORKTREE_MANAGER_FILE = CHATLABS_DIR / "worktree-manager.json"


@dataclass
class WorktreeInfo:
    """Worktree 信息"""
    story_id: str
    path: str  # 相对于 PROJECT_DIR
    branch: str
    status: str  # running | completed | failed | merged
    created_at: str
    merged: bool
    merged_at: Optional[str] = None
    description: Optional[str] = None


class WorktreeManager:
    """Worktree 生命周期管理器"""

    DEFAULT_MANAGER = {
        "version": "1.0",
        "worktrees": {},
        "main_branch": "master",
        "created_at": None
    }

    def __init__(self):
        self._data = self._load()
        if self._data["created_at"] is None:
            self._data["created_at"] = datetime.now(timezone.utc).isoformat()

    def _load(self) -> dict:
        """加载 manager 状态"""
        if WORKTREE_MANAGER_FILE.exists():
            try:
                return json.loads(WORKTREE_MANAGER_FILE.read_text())
            except (json.JSONDecodeError, KeyError):
                pass
        return {**self.DEFAULT_MANAGER}

    def save(self) -> None:
        """保存 manager 状态"""
        WORKTREE_MANAGER_FILE.parent.mkdir(parents=True, exist_ok=True)
        WORKTREE_MANAGER_FILE.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2)
        )

    def _sanitize_story_id(self, story_id: str) -> str:
        """将 story_id 转换为安全的目录名"""
        # STORY-001 -> story-001
        # 1140062001234567 -> story-1140062001234567
        if story_id.startswith("STORY-"):
            return story_id.lower()
        return f"story-{story_id}"

    def _run_git(self, args: list, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        """执行 git 命令"""
        return subprocess.run(
            ["git"] + args,
            capture_output=True, text=True,
            cwd=cwd or PROJECT_DIR
        )

    def create_worktree(
        self,
        story_id: str,
        description: Optional[str] = None,
        base_branch: Optional[str] = None
    ) -> WorktreeInfo:
        """
        创建新的 worktree

        Args:
            story_id: Story ID (如 STORY-001 或 1140062001234567)
            description: Story 描述
            base_branch: 基础分支，默认为 main_branch

        Returns:
            WorktreeInfo 对象

        Raises:
            ValueError: story_id 已存在
        """
        if story_id in self._data["worktrees"]:
            raise ValueError(f"Worktree for {story_id} already exists")

        # 生成 worktree 路径和分支名
        dir_name = self._sanitize_story_id(story_id)
        worktree_path = WORKTREES_ROOT / dir_name
        branch_name = f"wt/{dir_name}"

        # 使用指定基础分支或默认 main_branch
        base = base_branch or self._data["main_branch"]

        # 创建 worktree 目录
        WORKTREES_ROOT.mkdir(parents=True, exist_ok=True)

        # 执行 git worktree add
        result = self._run_git([
            "worktree", "add",
            "--branch", branch_name,
            str(worktree_path),
            base
        ])

        if result.returncode != 0:
            raise RuntimeError(f"git worktree add failed: {result.stderr}")

        # 初始化 worktree 内的 .chatlabs/ 目录
        wt_chatlabs = worktree_path / ".chatlabs"
        wt_chatlabs.mkdir(parents=True, exist_ok=True)

        # 复制必要的目录结构到 worktree
        self._init_worktree_artifacts(worktree_path, story_id)

        # 记录到 manager
        info = WorktreeInfo(
            story_id=story_id,
            path=str(worktree_path.relative_to(PROJECT_DIR)),
            branch=branch_name,
            status="created",
            created_at=datetime.now(timezone.utc).isoformat(),
            merged=False,
            description=description
        )

        self._data["worktrees"][story_id] = asdict(info)
        self.save()

        return info

    def _init_worktree_artifacts(self, worktree_path: Path, story_id: str) -> None:
        """初始化 worktree 内的 artifacts 目录"""
        # 创建 stories 目录结构
        wt_stories = worktree_path / ".chatlabs" / "stories" / story_id
        wt_stories.mkdir(parents=True, exist_ok=True)

        # 创建 state 目录
        wt_state = worktree_path / ".chatlabs" / "state"
        wt_state.mkdir(parents=True, exist_ok=True)

        # 创建 reports 目录
        wt_reports = worktree_path / ".chatlabs" / "reports"
        wt_reports.mkdir(parents=True, exist_ok=True)

    def list_worktrees(self) -> list[WorktreeInfo]:
        """列出所有 worktree"""
        worktrees = []
        for story_id, data in self._data["worktrees"].items():
            worktrees.append(WorktreeInfo(**data))
        return sorted(worktrees, key=lambda w: w.created_at)

    def get_worktree(self, story_id: str) -> Optional[WorktreeInfo]:
        """获取指定 story 的 worktree 信息"""
        if story_id in self._data["worktrees"]:
            return WorktreeInfo(**self._data["worktrees"][story_id])
        return None

    def update_status(self, story_id: str, status: str) -> None:
        """更新 worktree 状态"""
        if story_id in self._data["worktrees"]:
            self._data["worktrees"][story_id]["status"] = status
            self.save()

    def remove_worktree(self, story_id: str, force: bool = False) -> bool:
        """
        移除 worktree

        Args:
            story_id: Story ID
            force: 是否强制删除（忽略未合并状态）

        Returns:
            True if removed successfully
        """
        if story_id not in self._data["worktrees"]:
            return False

        info = WorktreeInfo(**self._data["worktrees"][story_id])
        worktree_path = PROJECT_DIR / info.path

        # 先从 git 移除 worktree
        result = self._run_git(["worktree", "remove", info.path])
        if result.returncode != 0 and not force:
            raise RuntimeError(
                f"git worktree remove failed: {result.stderr}\n"
                f"Use force=True to remove anyway"
            )

        # 如果 git remove 失败，手动清理
        if result.returncode != 0 and force:
            # 移除 worktree 目录
            if worktree_path.exists():
                shutil.rmtree(worktree_path)
            # 尝试删除分支
            self._run_git(["branch", "-D", info.branch])

        # 从 manager 中移除
        del self._data["worktrees"][story_id]
        self.save()

        return True

    def merge_to_master(
        self,
        story_id: str,
        commit_message: Optional[str] = None,
        delete_after: bool = True
    ) -> bool:
        """
        合并 worktree 到 master

        Args:
            story_id: Story ID
            commit_message: 提交信息
            delete_after: 合并后是否删除 worktree

        Returns:
            True if merged successfully
        """
        info = self.get_worktree(story_id)
        if not info:
            raise ValueError(f"No worktree found for {story_id}")

        if info.merged:
            raise ValueError(f"Worktree {story_id} already merged")

        # 检查 generator:all-done 事件
        wt_chatlabs = PROJECT_DIR / info.path / ".chatlabs"
        events_file = wt_chatlabs / "state" / "events.jsonl"

        if events_file.exists():
            with events_file.open() as f:
                events = [json.loads(line) for line in f if line.strip()]
            has_completion = any(
                e.get("type") == "generator:all-done"
                for e in events
            )
            if not has_completion:
                print(
                    f"[worktree-manager] Warning: No generator:all-done event found. "
                    f"Proceeding anyway..."
                )

        # 切换到 main repo
        result = self._run_git(["checkout", self._data["main_branch"]])
        if result.returncode != 0:
            raise RuntimeError(f"Failed to checkout {self._data['main_branch']}: {result.stderr}")

        # 合并分支
        msg = commit_message or f"Merge {story_id} ({info.description or 'worktree'})"
        result = self._run_git(["merge", "--no-ff", "-m", msg, info.branch])
        if result.returncode != 0:
            raise RuntimeError(f"Merge failed: {result.stderr}")

        # 更新状态
        self._data["worktrees"][story_id]["status"] = "merged"
        self._data["worktrees"][story_id]["merged"] = True
        self._data["worktrees"][story_id]["merged_at"] = datetime.now(timezone.utc).isoformat()
        self.save()

        # 删除 worktree
        if delete_after:
            self.remove_worktree(story_id, force=True)

        return True

    def cleanup_merged(self) -> int:
        """清理所有已合并的 worktree 目录"""
        count = 0
        for story_id, data in list(self._data["worktrees"].items()):
            if data.get("merged"):
                info = WorktreeInfo(**data)
                worktree_path = PROJECT_DIR / info.path
                if worktree_path.exists():
                    shutil.rmtree(worktree_path)
                del self._data["worktrees"][story_id]
                count += 1

        if count > 0:
            self.save()

        return count

    def get_status_summary(self) -> dict:
        """获取并行任务概览"""
        worktrees = self.list_worktrees()
        return {
            "total": len(worktrees),
            "running": sum(1 for w in worktrees if w.status == "running"),
            "completed": sum(1 for w in worktrees if w.status == "completed"),
            "merged": sum(1 for w in worktrees if w.merged),
            "worktrees": [asdict(w) for w in worktrees]
        }


# ── CLI Interface ──────────────────────────────────────────────────

def main():
    """CLI 入口"""
    import argparse

    parser = argparse.ArgumentParser(description="Worktree Manager")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # list
    subparsers.add_parser("list", help="列出所有 worktree")

    # status
    subparsers.add_parser("status", help="显示并行任务概览")

    # create
    create_parser = subparsers.add_parser("create", help="创建 worktree")
    create_parser.add_argument("story_id", help="Story ID")
    create_parser.add_argument("--description", "-d", help="Story 描述")

    # remove
    remove_parser = subparsers.add_parser("remove", help="移除 worktree")
    remove_parser.add_argument("story_id", help="Story ID")
    remove_parser.add_argument("--force", "-f", action="store_true", help="强制删除")

    # merge
    merge_parser = subparsers.add_parser("merge", help="合并到 master")
    merge_parser.add_argument("story_id", help="Story ID")
    merge_parser.add_argument("--message", "-m", help="提交信息")
    merge_parser.add_argument("--no-delete", action="store_true", help="合并后不删除 worktree")

    # cleanup
    subparsers.add_parser("cleanup", help="清理已合并的 worktree 目录")

    args = parser.parse_args()

    wm = WorktreeManager()

    if args.command == "list":
        worktrees = wm.list_worktrees()
        if not worktrees:
            print("No worktrees found.")
            return
        for w in worktrees:
            print(f"{w.story_id}: {w.path} ({w.status})")

    elif args.command == "status":
        summary = wm.get_status_summary()
        print(f"Total: {summary['total']}")
        print(f"  Running: {summary['running']}")
        print(f"  Completed: {summary['completed']}")
        print(f"  Merged: {summary['merged']}")

    elif args.command == "create":
        info = wm.create_worktree(args.story_id, args.description)
        print(f"Created worktree for {info.story_id}")
        print(f"  Path: {info.path}")
        print(f"  Branch: {info.branch}")
        print(f"  To start: cd {info.path} && claude")

    elif args.command == "remove":
        wm.remove_worktree(args.story_id, args.force)
        print(f"Removed worktree {args.story_id}")

    elif args.command == "merge":
        wm.merge_to_master(
            args.story_id,
            args.message,
            not args.no_delete
        )
        print(f"Merged {args.story_id} to {wm._data['main_branch']}")

    elif args.command == "cleanup":
        count = wm.cleanup_merged()
        print(f"Cleaned up {count} merged worktree(s)")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

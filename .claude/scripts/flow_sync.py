#!/usr/bin/env python3
"""
flow_sync.py — Flow 跨项目同步核心逻辑

在项目中管理 Flow 的关联、同步和版本。

Usage:
    from flow_sync import FlowSync
    fs = FlowSync(project_dir=Path("/workspace/project-a"))
    fs.link()                    # 关联项目到 Flow 仓库
    fs.status()                  # 查看同步状态
    fs.pull()                    # 拉取最新 Flow
    fs.push("feat: ...")         # 推送变更
"""
from __future__ import annotations
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from flow_repo import FlowRepo, get_default_flow_repo, DEFAULT_FLOW_REPO


# 默认 Flow 仓库本地路径
FLOW_CACHE_DIR = Path.home() / ".cache" / "chatlabs-flow"


@dataclass
class FlowSync:
    """Flow 跨项目同步管理器"""

    project_dir: Path
    flow_dir: Optional[Path] = None
    source_config_file: Optional[Path] = None

    def __post_init__(self):
        self.flow_dir = self.flow_dir or self.project_dir / ".chatlabs" / "flow"
        self.source_config_file = self.flow_dir / ".flow-source.json"

    # ── 配置读写 ─────────────────────────────────────────────

    def is_linked(self) -> bool:
        """检查项目是否已关联 Flow"""
        return self.source_config_file.exists()

    def get_config(self) -> Optional[dict]:
        """读取 Flow 来源配置"""
        if not self.is_linked():
            return None
        try:
            return json.loads(self.source_config_file.read_text())
        except Exception:
            return None

    def save_config(self, config: dict):
        """保存 Flow 来源配置"""
        self.flow_dir.mkdir(parents=True, exist_ok=True)
        self.source_config_file.write_text(
            json.dumps(config, indent=2, ensure_ascii=False)
        )

    def _create_default_config(self) -> dict:
        """创建默认配置"""
        repo = get_default_flow_repo()
        repo.ensure_local()

        return {
            "flow_repo": DEFAULT_FLOW_REPO,
            "local_path": str(repo.local_dir),
            "flow_branch": "master",
            "flow_version": repo.read_version() or "unknown",
            "last_commit": repo.get_current_commit() or "",
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
            "linked_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── 软链接管理 ─────────────────────────────────────────────

    def _get_claude_link(self) -> Path:
        """获取 .claude 软链接路径"""
        return self.flow_dir / ".claude"

    def _is_symlink_valid(self) -> bool:
        """检查软链接是否有效"""
        link = self._get_claude_link()
        if not link.is_symlink():
            return False
        # 检查链接目标是否存在
        return link.resolve().exists()

    def _create_symlink(self) -> tuple[bool, str]:
        """创建软链接到 Flow 仓库的 .claude 目录"""
        config = self.get_config()
        if not config:
            return False, "未找到 Flow 配置"

        local_path = Path(config["local_path"])
        if not local_path.exists():
            return False, f"Flow 仓库路径不存在: {local_path}"

        claude_dir = local_path / ".claude"
        if not claude_dir.exists():
            return False, f"Flow 仓库 .claude 目录不存在: {claude_dir}"

        link = self._get_claude_link()

        # 如果已存在软链接但无效，先删除
        if link.exists() and not self._is_symlink_valid():
            link.unlink()

        # 创建软链接
        try:
            if not link.exists():
                link.symlink_to(claude_dir)
            return True, f"软链接已创建 → {claude_dir}"
        except Exception as e:
            return False, f"创建软链接失败: {e}"

    def _fix_symlink_if_needed(self) -> tuple[bool, str]:
        """检查并修复软链接（如果仓库位置变了）"""
        if self._is_symlink_valid():
            return True, "软链接有效"

        return self._create_symlink()

    # ── 核心操作 ─────────────────────────────────────────────

    def link(self, force: bool = False) -> tuple[bool, str]:
        """关联项目到 Flow 仓库

        Args:
            force: 是否强制重新关联

        Returns:
            (success, message)
        """
        if self.is_linked() and not force:
            # 检查并修复软链接
            return self._fix_symlink_if_needed()

        # 确保 Flow 仓库本地存在
        repo = get_default_flow_repo()
        if not repo.exists():
            repo.clone()
            repo.fetch()

        # 创建配置
        config = self._create_default_config()
        self.save_config(config)

        # 创建软链接
        success, msg = self._create_symlink()

        if success:
            return True, f"""
✅ Flow 关联成功

仓库: {config['flow_repo']}
版本: v{config['flow_version']}
分支: {config['flow_branch']}
本地: {config['local_path']}
路径: {self.flow_dir.relative_to(self.project_dir) / '.claude'}

{msg}

提示: 运行 /flow-status 查看同步状态
"""

        return True, f"Flow 关联成功，但软链接创建失败: {msg}"

    def unlink(self, keep_files: bool = False) -> tuple[bool, str]:
        """取消项目与 Flow 的关联

        Args:
            keep_files: 是否保留 Flow 文件

        Returns:
            (success, message)
        """
        if not self.is_linked():
            return False, "项目未关联 Flow"

        link = self._get_claude_link()
        if link.is_symlink() or link.exists():
            if link.is_symlink():
                link.unlink()
            elif not keep_files:
                import shutil
                shutil.rmtree(link)

        if not keep_files and self.flow_dir.exists():
            import shutil
            shutil.rmtree(self.flow_dir)

        return True, "✅ 已取消 Flow 关联"

    def status(self) -> dict:
        """获取 Flow 同步状态"""
        if not self.is_linked():
            return {
                "linked": False,
                "message": "项目未关联 Flow，请运行 /flow-link",
            }

        config = self.get_config()
        if not config:
            return {
                "linked": False,
                "message": "Flow 配置损坏，请重新运行 /flow-link",
            }

        repo = FlowRepo(repo_url=config["flow_repo"], local_dir=Path(config["local_path"]))
        local_commit = repo.get_current_commit() or config.get("last_commit", "unknown")
        remote_commit = repo.get_remote_commit() or local_commit
        current_branch = repo.get_current_branch() or config.get("flow_branch", "master")
        diffs = repo.get_diff_summary() if repo.exists() else []
        tags = repo.get_tags()[:5] if repo.exists() else []

        return {
            "linked": True,
            "flow_repo": config["flow_repo"],
            "flow_branch": current_branch,
            "flow_version": config.get("flow_version", "unknown"),
            "local_commit": local_commit,
            "remote_commit": remote_commit,
            "has_updates": local_commit != remote_commit,
            "is_dirty": repo.is_dirty() if repo.exists() else False,
            "diff_count": len(diffs),
            "last_synced_at": config.get("last_synced_at", "从未同步"),
            "diffs": diffs[:10],  # 只返回前10个变更
            "recent_tags": tags,
            "symlink_valid": self._is_symlink_valid(),
            "local_path": config.get("local_path"),
        }

    def format_status(self) -> str:
        """格式化状态输出"""
        status = self.status()

        if not status["linked"]:
            return f"""
Flow 同步状态
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ 未关联

{status['message']}
"""

        lines = [
            "Flow 同步状态",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"仓库: {status['flow_repo']}",
            f"分支: {status['flow_branch']}",
            f"版本: v{status['flow_version']}",
            f"本地: {status['local_commit']}",
            f"远程: {status['remote_commit']}",
        ]

        if status["has_updates"]:
            lines.append(f"         ↑ 有更新可用")
        elif status["is_dirty"]:
            lines.append(f"         ⚠️ 有未提交的变更")
        else:
            lines.append(f"         ✓ 已同步")

        lines.extend([
            f"上次同步: {status['last_synced_at']}",
            "",
        ])

        # 软链接状态
        if not status["symlink_valid"]:
            lines.append("⚠️ 软链接无效，请运行 /flow-link 修复")
            lines.append("")

        # 未提交变更
        if status["diffs"]:
            lines.append("变更状态:")
            for diff in status["diffs"]:
                status_icon = {
                    "M": "📝", "A": "✨", "D": "🗑️",
                    "R": "🔄", "?": "❓",
                }.get(diff["status"][0], "•")
                lines.append(f"  {status_icon} {diff['file']}")
            lines.append("")

        # 提示
        if status["has_updates"]:
            lines.append("提示: 运行 /flow-pull 获取最新版本")
        elif status["is_dirty"]:
            lines.append("提示: 运行 /flow-push 推送变更")

        return "\n".join(lines)

    def pull(self, version: Optional[str] = None, force: bool = False) -> tuple[bool, str]:
        """从 Flow 仓库拉取最新变更

        Args:
            version: 指定版本（tag），None 表示拉取最新
            force: 是否强制覆盖本地修改

        Returns:
            (success, message)
        """
        if not self.is_linked():
            return False, "项目未关联 Flow"

        config = self.get_config()
        repo = FlowRepo(repo_url=config["flow_repo"], local_dir=Path(config["local_path"]))

        # 确保仓库存在
        if not repo.exists():
            repo.clone()

        # 修复软链接
        fix_ok, fix_msg = self._fix_symlink_if_needed()

        # 如果指定版本，切换到指定版本
        if version:
            ok, msg = repo.checkout(version)
            if not ok:
                return False, f"切换版本失败: {msg}"
        else:
            # 拉取最新
            if repo.is_dirty() and not force:
                ok, msg = repo.stash()
                if ok:
                    pull_ok, pull_msg = repo.pull()
                    if pull_ok:
                        repo.stash_pop()
                else:
                    return False, f"有未提交的变更，请先提交或使用 --force: {msg}"
            else:
                pull_ok, pull_msg = repo.pull()
                if not pull_ok:
                    return False, f"拉取失败: {pull_msg}"

        # 更新配置
        config["last_commit"] = repo.get_current_commit() or config.get("last_commit", "")
        config["flow_version"] = repo.read_version() or config.get("flow_version", "")
        config["last_synced_at"] = datetime.now(timezone.utc).isoformat()
        self.save_config(config)

        # 获取更新内容
        logs = repo.get_log(limit=5)

        lines = [f"📥 Flow 已更新"]
        lines.append(f"  版本: v{config['flow_version']}")
        lines.append(f"  Commit: {config['last_commit']}")
        if logs:
            lines.append("  更新内容:")
            for log in logs[:3]:
                lines.append(f"    - {log['message'][:60]}")
        lines.append("")
        lines.append("请重启 session 使变更生效")

        return True, "\n".join(lines)

    def push(self, message: str, author_name: Optional[str] = None,
             author_email: Optional[str] = None) -> tuple[bool, str, Optional[str]]:
        """推送 Flow 变更到 GitHub

        Args:
            message: 提交消息
            author_name: 作者名称
            author_email: 作者邮箱

        Returns:
            (success, message, commit_url)
        """
        if not self.is_linked():
            return False, "项目未关联 Flow", None

        config = self.get_config()
        repo = FlowRepo(repo_url=config["flow_repo"], local_dir=Path(config["local_path"]))

        # 确保仓库存在
        if not repo.exists():
            repo.clone()

        # 修复软链接
        self._fix_symlink_if_needed()

        # 提交并推送
        ok, msg, commit_hash = repo.push(
            message=message,
            author_name=author_name,
            author_email=author_email,
        )

        if not ok:
            return False, msg, None

        # 更新配置
        config["last_commit"] = commit_hash or config.get("last_commit", "")
        config["last_synced_at"] = datetime.now(timezone.utc).isoformat()
        self.save_config(config)

        commit_url = repo.get_commit_url(commit_hash) if commit_hash else ""

        return True, f"""
🚀 Flow 变更已推送

Commit: {commit_hash[:8] if commit_hash else '?'}
Message: {message}
分支: {config['flow_branch']}
URL: {commit_url}

其他项目可以使用 /flow-pull 同步此更新
""", commit_url

    def list_versions(self) -> list[dict]:
        """列出可用的 Flow 版本"""
        if not self.is_linked():
            config = self._create_default_config()
        else:
            config = self.get_config()

        repo = FlowRepo(repo_url=config["flow_repo"], local_dir=Path(config["local_path"]))

        if not repo.exists():
            repo.clone()

        # 如果没有版本信息，先 fetch
        if not repo.read_version():
            repo.fetch()

        # 获取标签作为版本
        tags = repo.get_tags()
        logs = repo.get_log(limit=20)

        versions = []
        current_commit = repo.get_current_commit()

        # 添加标签作为版本
        for tag in tags:
            versions.append({
                "version": tag,
                "type": "tag",
                "current": tag == repo.get_current_branch(),
            })

        # 添加最近的 commit
        for log in logs:
            if log["hash"] not in [v["version"] for v in versions]:
                # 统一使用 7 位 hash 比较
                is_current = current_commit and log["hash"].startswith(current_commit)
                versions.append({
                    "version": log["hash"],
                    "type": "commit",
                    "message": log["message"],
                    "date": log["date"],
                    "current": is_current,
                })

        return versions[:10]

    def format_versions(self) -> str:
        """格式化版本列表输出"""
        versions = self.list_versions()
        config = self.get_config() or {}

        # 获取 repo 实例读取 MANIFEST 版本
        from flow_repo import FlowRepo
        repo = FlowRepo(repo_url=config.get("flow_repo", DEFAULT_FLOW_REPO),
                       local_dir=Path(config.get("local_path", FLOW_CACHE_DIR / "dev-agent-flow")))
        manifest_version = config.get("flow_version") or repo.read_version()

        # 从 versions 中找到当前版本
        current_version = None

        # 优先使用 MANIFEST.md 中的版本号
        for v in versions:
            if v.get("current"):
                # 如果有 MANIFEST 版本号，用版本号；否则用 commit hash
                current_version = manifest_version or v["version"]
                break
        if not current_version:
            current_version = manifest_version or config.get("flow_version", "unknown")

        lines = [
            "Flow 版本列表",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"当前版本: v{current_version}",
            f"当前分支: {config.get('flow_branch', 'master')}",
            "",
        ]

        for v in versions:
            marker = " ← HEAD" if v.get("current") else ""
            lines.append(f"v{v['version']}{marker}")

        lines.append("")
        lines.append("使用 /flow-pull --version <版本> 切换")

        return "\n".join(lines)

    def get_commit_url(self, commit_hash: str) -> str:
        """获取 commit 的 GitHub URL"""
        config = self.get_config()
        if not config:
            return ""

        repo = FlowRepo(repo_url=config["flow_repo"])
        return repo.get_commit_url(commit_hash)


def get_flow_sync(project_dir: Optional[Path] = None) -> FlowSync:
    """获取 FlowSync 实例

    Args:
        project_dir: 项目目录，默认使用环境变量或当前目录

    Returns:
        FlowSync 实例
    """
    if project_dir is None:
        project_dir = Path(os.environ.get(
            "CLAUDE_PROJECT_DIR",
            Path.cwd()
        ))
    return FlowSync(project_dir=project_dir)


# CLI 入口
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Flow 跨项目同步工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # status 命令
    subparsers.add_parser("status", help="查看同步状态")

    # link 命令
    link_parser = subparsers.add_parser("link", help="关联项目到 Flow")
    link_parser.add_argument("--force", action="store_true", help="强制重新关联")

    # unlink 命令
    unlink_parser = subparsers.add_parser("unlink", help="取消关联")
    unlink_parser.add_argument("--keep-files", action="store_true", help="保留文件")

    # pull 命令
    pull_parser = subparsers.add_parser("pull", help="拉取最新 Flow")
    pull_parser.add_argument("--version", "-v", help="指定版本")
    pull_parser.add_argument("--force", action="store_true", help="强制覆盖")

    # push 命令
    push_parser = subparsers.add_parser("push", help="推送 Flow 变更")
    push_parser.add_argument("--message", "-m", required=True, help="提交消息")
    push_parser.add_argument("--author", help="作者名称")
    push_parser.add_argument("--email", help="作者邮箱")

    # version 命令
    version_parser = subparsers.add_parser("version", help="查看版本列表")

    args = parser.parse_args()
    fs = get_flow_sync()

    if args.command == "status":
        print(fs.format_status())
    elif args.command == "link":
        ok, msg = fs.link(force=args.force)
        print(msg)
    elif args.command == "unlink":
        ok, msg = fs.unlink(keep_files=args.keep_files)
        print(msg)
    elif args.command == "pull":
        ok, msg = fs.pull(version=args.version, force=args.force)
        print(msg)
    elif args.command == "push":
        ok, msg, _ = fs.push(
            message=args.message,
            author_name=args.author,
            author_email=args.email,
        )
        print(msg)
    elif args.command == "version":
        print(fs.format_versions())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

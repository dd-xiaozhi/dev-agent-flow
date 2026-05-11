#!/usr/bin/env python3
"""
contract-drift-check.py — 检测代码变更与契约版本是否同步

触发时机：pre-commit hook 或 Generator agent 编码前

逻辑：
  1. 扫描 staged / modified 的 API 相关文件
  2. 提取当前 contract.md frontmatter 的 hash
  3. 比对上次记录的 hash（存于 .chatlabs/state/contract_hash）
  4. 若 API 文件变了但 hash 没变 → 拒绝

用法：
  python3 .claude/scripts/contract-drift-check.py --staged    # pre-commit hook
  python3 .claude/scripts/contract-drift-check.py --changed   # Generator agent 用
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── 集中路径常量 ──────────────────────────────────────────────────
_PROJECT_DIR = Path(__file__).resolve().parents[2]
_CHATLABS_DIR = _PROJECT_DIR / ".chatlabs"
_STATE_DIR = _CHATLABS_DIR / "state"
_STORIES_DIR = _CHATLABS_DIR / "stories"
_HASH_STORE_FILE = _STATE_DIR / "contract_hash"


# ── 类型定义 ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class StoryContractHash:
    """Story 的契约 hash 记录。"""
    story_id: str
    hash: str
    updated_at: str


@dataclass
class DriftCheckResult:
    """契约漂移检查结果。"""
    status: str  # "drift" | "contract_bumped" | "first_change" | "version_lock_violation"
    story_id: str
    message: str
    changed_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "story_id": self.story_id,
            "message": self.message,
            "changed_files": self.changed_files,
        }


# ── API 文件检测（Deep Module）───────────────────────────────────

# API 相关文件检测模式
_API_PATTERNS = [
    re.compile(r"\b(handler|controller|router|endpoint|api)\b", re.IGNORECASE),
]
_API_EXTENSIONS = {".java", ".py", ".go", ".ts", ".js", ".rs"}


def is_api_file(path: Path) -> bool:
    """检测是否为 API 相关文件。"""
    # 文件名检测
    stem = path.stem.lower()
    if any(p.search(stem) for p in _API_PATTERNS):
        return True

    # 路径 + 扩展名检测（src/ 目录下的后端文件）
    if "src/" in str(path) and path.suffix.lower() in _API_EXTENSIONS:
        return True

    return False


def is_story_related(path: Path, story_id: str) -> bool:
    """检查文件是否与 story 相关。"""
    path_str = str(path)
    return story_id in path_str or is_api_file(path)


# ── 契约 Hash 管理（Deep Module）─────────────────────────────────

def extract_frontmatter_hash(md_path: Path) -> str:
    """从 markdown 文件提取 frontmatter 的 hash。"""
    text = md_path.read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return ""
    return hashlib.sha256(match.group(1).encode()).hexdigest()[:16]


class ContractHashStore:
    """契约 hash 存储管理器。"""

    def __init__(self, store_file: Path):
        self._file = store_file
        self._cache: Optional[dict] = None

    def load(self) -> dict[str, str]:
        """加载已存储的 hash 映射。"""
        if self._cache is not None:
            return self._cache

        if not self._file.exists():
            self._cache = {}
            return self._cache

        try:
            self._cache = json.loads(self._file.read_text())
        except Exception:
            self._cache = {}

        return self._cache

    def save(self, hashes: dict) -> None:
        """保存 hash 映射。"""
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps(hashes, ensure_ascii=False, indent=2))
        self._cache = hashes

    def get_hash(self, story_id: str) -> Optional[str]:
        """获取指定 story 的 hash。"""
        return self.load().get(story_id)

    def set_hash(self, story_id: str, hash_value: str) -> None:
        """设置指定 story 的 hash。"""
        hashes = self.load()
        hashes[story_id] = hash_value
        self.save(hashes)


# ── Git 操作（Deep Module）────────────────────────────────────────

@dataclass
class GitChange:
    """Git 变更文件。"""
    path: Path
    status: str  # A/M/D 等


def get_changed_files(mode: str = "staged") -> list[GitChange]:
    """获取 git 变更文件列表。

    Args:
        mode: "staged" 或 "changed"

    Returns:
        GitChange 列表
    """
    if mode == "staged":
        cmd = ["git", "diff", "--cached", "--name-status"]
    else:
        cmd = ["git", "diff", "--name-status"]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(_PROJECT_DIR), timeout=30
        )
        if result.returncode != 0:
            return []
    except Exception:
        return []

    changes = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        # git --name-status 格式: <status><tab><path>
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        status, path = parts
        changes.append(GitChange(path=_PROJECT_DIR / path, status=status))

    return changes


# ── Story 检查（Deep Module）─────────────────────────────────────

class StoryContractChecker:
    """Story 契约检查器。"""

    def __init__(self, story_dir: Path, hash_store: ContractHashStore):
        self._story_dir = story_dir
        self._hash_store = hash_store
        self._story_id = story_dir.name

    @property
    def contract_path(self) -> Path:
        return self._story_dir / "contract.md"

    def check(self, changed_files: list[GitChange]) -> Optional[DriftCheckResult]:
        """检查 story 契约是否漂移。"""
        if not self.contract_path.exists():
            return None

        # 过滤与 story 相关的变更文件
        related_changes = [
            c for c in changed_files
            if is_story_related(c.path, self._story_id)
        ]
        if not related_changes:
            return None

        # 提取当前契约 hash
        current_hash = extract_frontmatter_hash(self.contract_path)
        stored_hash = self._hash_store.get_hash(self._story_id)

        if not stored_hash:
            # 首次变更
            self._hash_store.set_hash(self._story_id, current_hash)
            return DriftCheckResult(
                status="first_change",
                story_id=self._story_id,
                message="首次 API 变更，已记录契约 hash",
            )

        if current_hash != stored_hash:
            return DriftCheckResult(
                status="contract_bumped",
                story_id=self._story_id,
                message="契约已同步更新",
            )

        # drift
        return DriftCheckResult(
            status="drift",
            story_id=self._story_id,
            message="API 变更但契约未更新",
            changed_files=[str(c.path.relative_to(_PROJECT_DIR)) for c in related_changes],
        )


# ── Spec 版本锁定检查（Deep Module）──────────────────────────────

@dataclass
class SpecContractRef:
    """Spec.md 中的 contract_ref 数据。"""
    story_id: str
    hash: str
    version: Optional[str] = None


def parse_frontmatter(text: str) -> dict:
    """解析 markdown frontmatter。"""
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    # 简单解析 YAML（实际使用中可用 pyyaml）
    result = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        result[key.strip()] = value.strip()
    return result


def extract_contract_ref(spec_path: Path) -> Optional[SpecContractRef]:
    """从 spec.md 提取 contract_ref 信息。"""
    if not spec_path.exists():
        return None

    try:
        text = spec_path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if not match:
            return None

        # 查找 contract_ref 块
        contract_ref_match = re.search(
            r"contract_ref:\s*\n((?:\s+\w+.*\n)*)", match.group(1)
        )
        if not contract_ref_match:
            return None

        ref_block = contract_ref_match.group(1)
        ref_data = {}
        for line in ref_block.splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                ref_data[key.strip()] = value.strip()

        if "story_id" in ref_data and "hash" in ref_data:
            return SpecContractRef(
                story_id=ref_data["story_id"],
                hash=ref_data["hash"],
                version=ref_data.get("version"),
            )
    except Exception:
        pass

    return None


def check_spec_version_lock(
    spec_path: Path,
    hash_store: ContractHashStore,
) -> Optional[DriftCheckResult]:
    """检查 spec.md 契约版本锁定。"""
    ref = extract_contract_ref(spec_path)
    if not ref:
        return None

    stored_hash = hash_store.get_hash(ref.story_id)

    if not stored_hash:
        return DriftCheckResult(
            status="version_lock_violation",
            story_id=ref.story_id,
            message=f"契约 hash 未记录，无法验证 spec 锁定",
        )

    if ref.hash != stored_hash:
        return DriftCheckResult(
            status="version_lock_violation",
            story_id=ref.story_id,
            message=f"契约版本不匹配：spec 要求 hash={ref.hash[:8]}...，实际={stored_hash[:8] if stored_hash else 'unknown'}...",
        )

    return None


# ── 主逻辑 ──────────────────────────────────────────────────────

def run(mode: str = "staged") -> list[DriftCheckResult]:
    """运行契约漂移检查。"""
    changes = get_changed_files(mode)
    if not changes:
        return []

    results: list[DriftCheckResult] = []
    hash_store = ContractHashStore(_HASH_STORE_FILE)

    # 检查 spec.md 版本锁定
    for change in changes:
        if change.path.name == "spec.md":
            result = check_spec_version_lock(change.path, hash_store)
            if result:
                results.append(result)

    # 检查各 story 契约漂移
    if not _STORIES_DIR.exists():
        return results

    for story_dir in sorted(_STORIES_DIR.iterdir()):
        if not story_dir.is_dir() or story_dir.name.startswith("."):
            continue

        checker = StoryContractChecker(story_dir, hash_store)
        result = checker.check(changes)
        if result:
            results.append(result)

    return results


def main() -> None:
    mode = "staged" if "--staged" in sys.argv else "changed"
    results = run(mode)

    drifts = [r for r in results if r.status == "drift"]

    if drifts:
        for r in drifts:
            print(f"FAIL {r.story_id}: {r.message}", file=sys.stderr)
            print(f"   变更文件: {', '.join(r.changed_files)}", file=sys.stderr)
        print("\n[contract-drift] 拒绝：API 变更未同步到契约", file=sys.stderr)
        print("  解决：先 bump contract.md version 再提交", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
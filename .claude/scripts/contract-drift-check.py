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

import hashlib
import json
import re
import subprocess
import sys
import os
from pathlib import Path

# Import centralized path constants
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from paths import PROJECT_DIR, CONTRACT_HASH, STORIES_DIR  # noqa: E402

HASH_STORE = CONTRACT_HASH


def extract_frontmatter_hash(md_path: Path) -> str:
    text = md_path.read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return ""
    return hashlib.sha256(match.group(1).encode()).hexdigest()[:16]


def load_stored_hashes() -> dict:
    if not HASH_STORE.exists():
        return {}
    try:
        return json.loads(HASH_STORE.read_text())
    except Exception:
        return {}


def save_stored_hashes(hashes: dict):
    HASH_STORE.parent.mkdir(parents=True, exist_ok=True)
    HASH_STORE.write_text(json.dumps(hashes, ensure_ascii=False, indent=2))


def get_changed_files(mode: str) -> list[Path]:
    if mode == "staged":
        cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"]
    else:
        cmd = ["git", "diff", "--name-only", "--diff-filter=ACM"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                cwd=str(PROJECT_DIR), timeout=30)
        if result.returncode != 0:
            return []
    except Exception:
        return []

    return [PROJECT_DIR / p for p in result.stdout.strip().splitlines() if p]


def is_api_file(path: Path) -> bool:
    """检测是否为 API 相关文件"""
    name = path.name.lower()
    stem = path.stem.lower()
    if name in ("openapi.yaml", "swagger.yaml", "swagger.yml"):
        return True
    if any(k in stem for k in ("handler", "controller", "router", "endpoint", "api")):
        return True
    if "src/" in str(path) and any(ext in name for ext in (".java", ".py", ".go", ".ts")):
        return True
    return False


def check_story(story_dir: Path, changed_files: list[Path]) -> dict:
    contract_path = story_dir / "contract.md"
    if not contract_path.exists():
        return None

    story_id = story_dir.name
    api_changed = [f for f in changed_files if story_id in str(f) or is_api_file(f)]

    if not api_changed:
        return None

    current_hash = extract_frontmatter_hash(contract_path)
    stored = load_stored_hashes()
    stored_hash = stored.get(story_id, "")

    if not stored_hash:
        stored[story_id] = current_hash
        save_stored_hashes(stored)
        return {
            "status": "first_change",
            "story_id": story_id,
            "message": "首次 API 变更，已记录契约 hash"
        }

    if current_hash != stored_hash:
        return {
            "status": "contract_bumped",
            "story_id": story_id,
            "message": "契约已同步更新"
        }

    return {
        "status": "drift",
        "story_id": story_id,
        "changed_files": [str(f.relative_to(PROJECT_DIR)) for f in api_changed],
        "message": "API 变更但契约未更新"
    }


def run(mode: str = "staged") -> list:
    stories_dir = STORIES_DIR
    if not stories_dir.exists():
        return []

    changed = get_changed_files(mode)
    results = []
    for story_dir in sorted(stories_dir.iterdir()):
        if story_dir.is_dir() and story_dir.name != ".DS_Store":
            r = check_story(story_dir, changed)
            if r:
                results.append(r)
    return results


def main():
    mode = "staged" if "--staged" in sys.argv else "changed"
    results = run(mode)

    drift = [r for r in results if r["status"] == "drift"]

    if drift:
        for r in drift:
            print(f"FAIL {r['story_id']}: {r['message']}", file=sys.stderr)
            print(f"   变更文件: {', '.join(r['changed_files'])}", file=sys.stderr)
        print("\n[contract-drift] 拒绝：API 变更未同步到契约", file=sys.stderr)
        print("  解决：先 bump contract.md version 再提交", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()

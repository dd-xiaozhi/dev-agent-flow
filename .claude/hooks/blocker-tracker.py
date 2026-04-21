#!/usr/bin/env python3
"""
blocker-tracker.py — 工具层 Blocker 自动追踪

事件：PostToolUse（Bash，exit_code != 0）
行为：检测到工具执行失败 → 自动追加到 blockers.md

前置条件：.chatlabs/state/current_task 文件存在（由命令层写入 task_id）
降级：exit_code == 0 / 无 active task → 直接退出

Blocker 类型自动判断：
  - mvn / gradle / javac 编译失败 → 环境-编译
  - 包含 'test' 命令 → 执行-测试
  - 'permission denied' → 环境-权限
  - 'connection refused' / 'ConnectionError' / 'ECONNREFUSED' → 环境-网络
  - 'not found' / 'command not found' → 环境-命令不存在
  - 其他 → 未知
"""
import sys
import json
import os
import re
from datetime import datetime
from pathlib import Path

# Import centralized path constants
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from paths import CURRENT_TASK, TASK_REPORTS  # noqa: E402

CURRENT_TASK_FILE = CURRENT_TASK
REPORTS_DIR = TASK_REPORTS


def get_active_task_id() -> str | None:
    try:
        return CURRENT_TASK_FILE.read_text().strip() or None
    except FileNotFoundError:
        return None


def infer_blocker_type(command: str, output: str) -> tuple[str, str]:
    """推断 Blocker 类型和子类型"""
    combined = (command + " " + output).lower()

    if re.search(r"\b(mvn|gradle|javac|ant|sbt)\b", combined):
        if "test" in combined:
            return "执行", "测试"
        return "环境", "编译"
    if "test" in combined and ("pytest" in combined or "jest" in combined
                                or "unittest" in combined or "junit" in combined):
        return "执行", "测试"
    if re.search(r"permission denied|chmod|chown", combined):
        return "环境", "权限"
    if re.search(r"connection refused|connectionerror|econnrefused|etimedout|network is unreachable", combined):
        return "环境", "网络"
    if re.search(r"not found|command not found|enoent|file does not exist", combined):
        return "环境", "命令不存在"
    if re.search(r"jsondecodeerror|yamlerror|syntaxerror|parse error", combined):
        return "环境", "配置错误"
    if re.search(r"git (merge|conflict|rebase)", combined):
        return "执行", "版本控制"
    return "未知", "未知"


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")


def count_blockers(blockers_file: Path) -> int:
    """统计 blockers.md 中的总条目数（排除统计行）"""
    if not blockers_file.exists():
        return 0
    return sum(1 for line in blockers_file.read_text().splitlines()
               if line.startswith("## ") and "[Hook-auto]" in line)


def append_blocker(task_id: str, command: str, exit_code: int, output: str):
    """追加 Blocker 条目到 blockers.md"""
    category, subcategory = infer_blocker_type(command, output)
    blocker_type = f"{category}-{subcategory}"

    short_output = output.strip()[:300] if output.strip() else "(无输出)"
    description = short_output.splitlines()[0] if short_output else "未知错误"

    entry = f"""## {ts()} [Hook-auto]
- **类型**: {blocker_type}
- **工具**: Bash
- **命令**: `{command[:150]}{'...' if len(command) > 150 else ''}`
- **Exit**: `{exit_code}` 
- **描述**: {description}
- **根因**: （待 Agent 补充）
- **解决状态**: 待解决
- **解决方案**: （待 Agent 填写）

---
"""

    td = REPORTS_DIR / task_id
    blockers_file = td / "blockers.md"

    if blockers_file.exists():
        content = blockers_file.read_text()
        marker = "## 统计"
        if marker in content:
            idx = content.index(marker)
            content = content[:idx] + entry + content[idx:]
        else:
            content = content + entry
        blockers_file.write_text(content)
    else:
        blockers_file.write_text(
            f"# {task_id} 阻塞点记录\n\n"
            "> 由 blocker-tracker.py 自动生成\n\n"
            + entry
            + "\n## 统计\n"
            f"- **总 blocker 数**: 1\n"
            "- **已解决**: 0\n"
            "- **待解决**: 1\n"
        )

    total = count_blockers(blockers_file)
    _update_stats(blockers_file, total)


def _update_stats(blockers_file: Path, total: int):
    """更新 blockers.md 的统计行"""
    if not blockers_file.exists():
        return
    content = blockers_file.read_text()
    lines = content.splitlines()
    new_lines = []
    for line in lines:
        if "**总 blocker 数**" in line:
            new_lines.append(f"- **总 blocker 数**: {total}")
        elif "**待解决**" in line:
            new_lines.append(f"- **待解决**: {total}")
        else:
            new_lines.append(line)
    blockers_file.write_text("\n".join(new_lines))

    task_id = blockers_file.parent.name
    _update_meta(task_id, total)


def _update_meta(task_id: str, blocker_count: int):
    """更新 meta.json 和 _index.jsonl"""
    import json as _json
    td = REPORTS_DIR / task_id
    meta_file = td / "meta.json"
    index_file = REPORTS_DIR / "_index.jsonl"
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")

    if meta_file.exists():
        try:
            meta = _json.loads(meta_file.read_text())
            meta["blocker_count"] = blocker_count
            meta["updated_at"] = now
            meta_file.write_text(_json.dumps(meta, indent=2, ensure_ascii=False))
        except Exception:
            pass

    if index_file.exists():
        try:
            lines = index_file.read_text().strip().splitlines()
            new_lines = []
            for line in lines:
                try:
                    entry = _json.loads(line)
                    if entry.get("task_id") == task_id:
                        entry["blocker_count"] = blocker_count
                        entry["updated_at"] = now
                    new_lines.append(_json.dumps(entry, ensure_ascii=False))
                except _json.JSONDecodeError:
                    new_lines.append(line)
            index_file.write_text("\n".join(new_lines) + "\n")
        except Exception:
            pass


def main():
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool = hook_input.get("tool", "")
    exit_code = hook_input.get("exit_code", 0)
    command = hook_input.get("command", "")
    output = hook_input.get("output", "") or ""

    if tool != "Bash" or exit_code == 0:
        sys.exit(0)

    task_id = get_active_task_id()
    if not task_id:
        sys.exit(0)

    td = REPORTS_DIR / task_id
    if not td.exists():
        sys.exit(0)

    append_blocker(task_id, command, exit_code, output)


if __name__ == "__main__":
    main()

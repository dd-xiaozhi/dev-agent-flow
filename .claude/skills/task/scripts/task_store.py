"""
task_store.py — task.json 单一写者门面（SSOT）

每个任务目录（.chatlabs/task/store/<story_id>/ 或 .chatlabs/task/bug-fix/<bug_id>/）
下的 task.json 是该任务的唯一状态文件，聚合 4 个 section + 顶层事件流：

  workflow → 流程编排状态（flow/phase/verdicts/blockers，任务级 SSOT）
  git      → 分支绑定（branch/worktree_path/source_branch/merge_targets）
  tapd     → TAPD 工单缓存（原 .chatlabs/tapd/tickets/<id>.json 的 local_mapping/subtasks）
  meta     → 任务元数据（task_id/created_at/trigger/dev_mode）
  bug_fix  → 仅 task_type == "bug-fix" 时存在（severity/fix_mode/linked_story_id 等）
  events   → 任务级事件流（替代 .chatlabs/state/events.jsonl，append-only）

设计原则：
- 所有 task.json 读写都过 TaskJsonStore，禁止其他脚本直写
- 写入用 atomic rename（写 .tmp → rename）+ fcntl 文件锁（防多进程竞态）
- section 级 partial update，避免无关字段被覆盖

Usage:
    store = TaskJsonStore.load_by_story("04-30-wechat-login")
    store.update_workflow({"phase": "implement", "current_step": "generator"})
    store.update_git({"branch": "feature/04-30-wechat-login", "branch_type": "feature"})
    store.save()

    # 跨任务查询
    task = TaskJsonStore.find_by_branch("feature/12345-x")
    bug_task = TaskJsonStore.find_by_tapd_id("67890")
    active = TaskJsonStore.list_active()
"""
from __future__ import annotations

import fcntl
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

# 项目根（CLAUDE_PROJECT_DIR 优先,否则按 .claude/skills/task/scripts/ 回退 4 级）
PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).resolve().parents[4])
))
TASK_DIR = PROJECT_DIR / ".chatlabs" / "task"
STORE_DIR = TASK_DIR / "store"
BUG_FIX_DIR = TASK_DIR / "bug-fix"

TASK_JSON_FILENAME = "task.json"

# task.json 默认骨架。未启用的 section 保持 None（而非空 dict），便于区分"未填充" vs "已填充但空"。
#
# meta.json 已废除（2026-05-27），原字段全部迁入 task.json：
#   - task_id / story_id / created_at / updated_at / trigger / dev_mode → 顶层（本骨架）
#   - tapd_ticket_id → tapd.ticket_id
#   - phase / agent / flow_id → workflow.phase / workflow.agent / workflow.flow.flow_id
#   - predecessor_task_id / tags → 顶层（本骨架新增）
#   - blocker_count / verdict / summary → workflow.blocker_count / workflow.verdict / workflow.summary
#     （按需写入，不在 DEFAULT 中预声明；summary 结构：
#      {completed_at, execution_log, key_decisions, deliverables, acceptance}）
DEFAULT_TASK_JSON: dict = {
    "task_id": None,            # {MM}-{dd}-{description}（如 05-20-sf-account-merge）
    "task_type": None,          # "store" | "bug-fix"
    "story_id": None,           # 业务 ID 或 bug ID
    "created_at": None,
    "updated_at": None,
    "trigger": None,            # first-start | defect-fix | manual | requirement-change
    "dev_mode": None,           # vibe | plan | spec
    "predecessor_task_id": None,  # 前驱 task_id(追溯链)
    "tags": [],                   # 任务标签（list[str]）

    "workflow": None,           # {flow_id, phase, agent, current_step, blockers, verdicts, flow,
                                #  blocker_count, verdict, summary}
    "git": None,                # {branch, branch_type, worktree_path, source_branch, merge_targets}
    "tapd": None,               # {ticket_id, entity_type, wiki_id, subtasks, ...}
    "bug_fix": None,            # 仅 task_type == "bug-fix"
    "events": None,             # list[dict]，append-only；None 表示尚未发布过事件
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskJsonStore:
    """task.json 的读写门面。一个实例对应一个 task.json 文件。

    构造方式：
      - load(task_dir)              直接给目录路径
      - load_by_story(story_id)     通过 story_id 在 STORE_DIR 下定位
      - load_by_bug(bug_id)         通过 bug_id 在 BUG_FIX_DIR 下定位
      - create(task_dir, task_type, story_id, **meta)  幂等创建（已存在则 load）
    """

    def __init__(self, task_dir: Path, data: dict) -> None:
        self.task_dir = task_dir
        self.path = task_dir / TASK_JSON_FILENAME
        self._data: dict = {**DEFAULT_TASK_JSON, **data}

    # ── 构造 ──────────────────────────────────────────────────────

    @classmethod
    def load(cls, task_dir: Path) -> "TaskJsonStore":
        """从指定目录加载 task.json。缺失时返回带默认骨架的实例（不写盘）。"""
        path = task_dir / TASK_JSON_FILENAME
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}
        return cls(task_dir, data)

    @classmethod
    def load_by_story(cls, story_id: str) -> "TaskJsonStore":
        return cls.load(STORE_DIR / story_id)

    @classmethod
    def load_by_bug(cls, bug_id: str) -> "TaskJsonStore":
        return cls.load(BUG_FIX_DIR / bug_id)

    @classmethod
    def create(
        cls,
        task_dir: Path,
        task_type: str,
        story_id: str,
        task_id: Optional[str] = None,
        trigger: Optional[str] = None,
        dev_mode: Optional[str] = None,
    ) -> "TaskJsonStore":
        """幂等创建：目录与 task.json 都不存在时初始化；已存在则 load。"""
        store = cls.load(task_dir)
        if store._data.get("task_id"):
            return store  # 已存在
        task_dir.mkdir(parents=True, exist_ok=True)
        ts = now_iso()
        store._data.update({
            "task_id": task_id,
            "task_type": task_type,
            "story_id": story_id,
            "created_at": ts,
            "updated_at": ts,
            "trigger": trigger,
            "dev_mode": dev_mode,
        })
        store.save()
        return store

    # ── section 读 ────────────────────────────────────────────────

    @property
    def data(self) -> dict:
        """返回 task.json 的完整 dict（只读视图，外部勿修改）。"""
        return self._data

    def get_workflow(self) -> Optional[dict]:
        return self._data.get("workflow")

    def get_git(self) -> Optional[dict]:
        return self._data.get("git")

    def get_tapd(self) -> Optional[dict]:
        return self._data.get("tapd")

    def get_bug_fix(self) -> Optional[dict]:
        return self._data.get("bug_fix")

    # ── section 写（partial update）────────────────────────────────

    def update_workflow(self, patch: dict) -> None:
        """workflow section 增量更新（旧值与 patch 浅合并）。"""
        cur = self._data.get("workflow") or {}
        cur.update(patch)
        self._data["workflow"] = cur

    def update_git(self, patch: dict) -> None:
        cur = self._data.get("git") or {}
        cur.update(patch)
        self._data["git"] = cur

    def update_tapd(self, patch: dict) -> None:
        cur = self._data.get("tapd") or {}
        cur.update(patch)
        self._data["tapd"] = cur

    def update_bug_fix(self, patch: dict) -> None:
        cur = self._data.get("bug_fix") or {}
        cur.update(patch)
        self._data["bug_fix"] = cur

    def set_field(self, key: str, value) -> None:
        """更新顶层字段（task_id / dev_mode / trigger 等）。"""
        self._data[key] = value

    # ── events（append-only 事件流）─────────────────────────────────

    def append_event(self, event_type: str, data: Optional[dict] = None) -> dict:
        """追加一条事件到 events 列表（不自动 save）。

        Args:
            event_type: 事件类型，如 "planner:all-cases-ready"
            data: 额外字段（story_id / actor / 等），与 ts/type 合并

        Returns:
            刚追加的事件 dict（已含 ts/type）
        """
        cur = self._data.get("events")
        if cur is None:
            cur = []
            self._data["events"] = cur
        event: dict = {"ts": now_iso(), "type": event_type}
        if data:
            # data 内已有 ts/type 会被覆盖（保证顶层字段权威）
            for k, v in data.items():
                if k in ("ts", "type"):
                    continue
                event[k] = v
        cur.append(event)
        return event

    def get_events(self, event_type: Optional[str] = None) -> list[dict]:
        """读取 events 列表（可按 type 过滤）。events 未初始化时返回空列表。"""
        cur = self._data.get("events") or []
        if event_type is None:
            return list(cur)
        return [e for e in cur if e.get("type") == event_type]

    # ── 持久化 ────────────────────────────────────────────────────

    def save(self) -> None:
        """原子写入：写 .tmp → fsync → rename。带 fcntl 排他锁防并发。"""
        self.task_dir.mkdir(parents=True, exist_ok=True)
        self._data["updated_at"] = now_iso()
        tmp = self.path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
                f.flush()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        tmp.replace(self.path)

    def to_dict(self) -> dict:
        return dict(self._data)

    # ── 跨任务查询（类方法）────────────────────────────────────────

    @classmethod
    def iter_all(cls) -> Iterator["TaskJsonStore"]:
        """遍历所有任务目录（store/ + bug-fix/）。"""
        for root in (STORE_DIR, BUG_FIX_DIR):
            if not root.exists():
                continue
            for sub in sorted(root.iterdir()):
                if not sub.is_dir():
                    continue
                if not (sub / TASK_JSON_FILENAME).exists():
                    continue
                yield cls.load(sub)

    @classmethod
    def find_by_branch(cls, branch: str) -> Optional["TaskJsonStore"]:
        for store in cls.iter_all():
            git = store.get_git() or {}
            if git.get("branch") == branch:
                return store
        return None

    @classmethod
    def find_by_story_id(cls, story_id: str) -> Optional["TaskJsonStore"]:
        """根据 story_id 查找任务（搜索 store/ 和 bug-fix/ 目录）。"""
        for root in (STORE_DIR, BUG_FIX_DIR):
            task_dir = root / story_id
            if task_dir.exists() and (task_dir / TASK_JSON_FILENAME).exists():
                return cls.load(task_dir)
        return None

    @classmethod
    def find_by_task_id(cls, task_id: str) -> Optional["TaskJsonStore"]:
        """根据 task_id 查找任务（遍历 store/ 与 bug-fix/，匹配 task.json.task_id）。

        task_id 与 story_id 在新约定下通常一致（task_id == story_id == {MM-dd}-{slug}），
        但仍允许不同（如同日重名兜底加时间戳后缀）。此方法兼容两种情形。
        """
        for store in cls.iter_all():
            if store._data.get("task_id") == task_id:
                return store
        return None

    @classmethod
    def find_by_tapd_id(cls, ticket_id: str) -> Optional["TaskJsonStore"]:
        ticket_id = str(ticket_id)
        for store in cls.iter_all():
            tapd = store.get_tapd() or {}
            if str(tapd.get("ticket_id") or "") == ticket_id:
                return store
        return None

    @classmethod
    def list_active(cls) -> list[dict]:
        """列出所有未 done 的任务（workflow.phase != 'done' 且 flow 未 terminal）。"""
        out: list[dict] = []
        for store in cls.iter_all():
            wf = store.get_workflow() or {}
            phase = wf.get("phase")
            if phase == "done":
                continue
            flow = wf.get("flow") or {}
            if flow.get("completed_at"):
                continue
            out.append({
                "task_id": store._data.get("task_id"),
                "task_type": store._data.get("task_type"),
                "story_id": store._data.get("story_id"),
                "phase": phase,
                "branch": (store.get_git() or {}).get("branch"),
                "task_dir": str(store.task_dir.relative_to(PROJECT_DIR)),
            })
        return out


# ── CLI（调试与脚本调用入口）────────────────────────────────────────

def _main() -> int:
    """简易 CLI：python task_store.py <show|list-active|find-branch|find-tapd> [arg]"""
    import argparse
    parser = argparse.ArgumentParser(description="TaskJsonStore CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="show <story_id|bug:bug_id>")
    p_show.add_argument("ref")

    sub.add_parser("list-active", help="list active tasks")

    p_fb = sub.add_parser("find-branch", help="find by branch")
    p_fb.add_argument("branch")

    p_ft = sub.add_parser("find-tapd", help="find by tapd ticket_id")
    p_ft.add_argument("ticket_id")

    args = parser.parse_args()

    if args.cmd == "show":
        ref = args.ref
        if ref.startswith("bug:"):
            store = TaskJsonStore.load_by_bug(ref[4:])
        else:
            store = TaskJsonStore.load_by_story(ref)
        print(json.dumps(store.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "list-active":
        print(json.dumps(TaskJsonStore.list_active(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "find-branch":
        store = TaskJsonStore.find_by_branch(args.branch)
        print(json.dumps(store.to_dict() if store else None, ensure_ascii=False, indent=2))
        return 0 if store else 1

    if args.cmd == "find-tapd":
        store = TaskJsonStore.find_by_tapd_id(args.ticket_id)
        print(json.dumps(store.to_dict() if store else None, ensure_ascii=False, indent=2))
        return 0 if store else 1

    return 1


if __name__ == "__main__":
    sys.exit(_main())

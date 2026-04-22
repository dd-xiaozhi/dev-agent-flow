"""
workflow-state.py — 工作流状态读写工具

提供统一的状态读写接口，替代分散的 ticket.json + meta.json。

Usage:
    from workflow_state import WorkflowState
    ws = WorkflowState.load()
    ws.update_phase("planner")
    ws.add_verdict("CASE-01", "PASS")
    ws.save()
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import STATE_DIR, STORIES_DIR


class WorkflowState:
    """工作流状态管理器"""

    DEFAULT_STATE = {
        "task_id": None,
        "story_id": None,
        "phase": None,
        "agent": None,
        "integrations": {
            "tapd": {
                "enabled": False,
                "ticket_id": None,
                "consensus_version": 0,
                "subtask_emitted": False,
                "last_synced_at": None
            }
        },
        "artifacts": {
            "contract": {"path": None, "version": None, "hash": None},
            "spec": {"path": None, "version": None}
        },
        "verdicts": {},  # case_id -> PASS/FAIL
        "blocker_count": 0,
        "updated_at": None
    }

    def __init__(self, data: dict):
        self._data = {**self.DEFAULT_STATE, **data}
        self._dirty = False

    @classmethod
    def load(cls, story_id: Optional[str] = None) -> "WorkflowState":
        """加载工作流状态"""
        state_file = cls._get_state_file(story_id)
        if state_file and state_file.exists():
            try:
                data = json.loads(state_file.read_text())
                return cls(data)
            except (json.JSONDecodeError, KeyError):
                pass
        return cls({})

    @classmethod
    def _get_state_file(cls, story_id: Optional[str] = None) -> Optional[Path]:
        """获取状态文件路径"""
        if story_id:
            story_dir = STORIES_DIR / story_id
            return story_dir / "workflow-state.json"
        # 默认读取 .chatlabs/state/workflow-state.json
        return STATE_DIR / "workflow-state.json"

    @classmethod
    def init_for_story(cls, story_id: str, task_id: str) -> "WorkflowState":
        """为新 story 初始化状态"""
        state_file = cls._get_state_file(story_id)
        if state_file:
            state_file.parent.mkdir(parents=True, exist_ok=True)

        state = cls({
            "task_id": task_id,
            "story_id": story_id,
            "phase": "doc-librarian",
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        return state

    def save(self, story_id: Optional[str] = None) -> None:
        """保存状态到文件"""
        self._data["updated_at"] = datetime.now(timezone.utc).isoformat()
        state_file = self._get_state_file(story_id)
        if state_file:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(json.dumps(self._data, ensure_ascii=False, indent=2))

    def update_phase(self, phase: str, agent: Optional[str] = None) -> None:
        """更新阶段"""
        self._data["phase"] = phase
        if agent:
            self._data["agent"] = agent
        self._dirty = True

    def set_artifacts(self, artifact_type: str, **kwargs) -> None:
        """设置 artifacts（contract/spec）"""
        if artifact_type not in self._data["artifacts"]:
            self._data["artifacts"][artifact_type] = {}
        self._data["artifacts"][artifact_type].update(kwargs)
        self._dirty = True

    def add_verdict(self, case_id: str, verdict: str) -> None:
        """添加 verdict"""
        self._data["verdicts"][case_id] = verdict
        self._dirty = True

    def all_verdicts_pass(self) -> bool:
        """检查是否所有 verdict 都是 PASS"""
        return all(v == "PASS" for v in self._data["verdicts"].values())

    def set_tapd_enabled(self, enabled: bool, ticket_id: Optional[str] = None) -> None:
        """设置 TAPD 集成状态"""
        self._data["integrations"]["tapd"]["enabled"] = enabled
        if ticket_id:
            self._data["integrations"]["tapd"]["ticket_id"] = ticket_id
        self._dirty = True

    def bump_consensus_version(self) -> int:
        """递增 consensus_version"""
        self._data["integrations"]["tapd"]["consensus_version"] += 1
        self._data["integrations"]["tapd"]["last_synced_at"] = datetime.now(timezone.utc).isoformat()
        self._dirty = True
        return self._data["integrations"]["tapd"]["consensus_version"]

    def set_subtask_emitted(self, emitted: bool) -> None:
        """设置 subtask 是否已派发"""
        self._data["integrations"]["tapd"]["subtask_emitted"] = emitted
        self._dirty = True

    def increment_blocker(self) -> None:
        """增加 blocker 计数"""
        self._data["blocker_count"] += 1
        self._dirty = True

    def to_dict(self) -> dict:
        """导出 dict"""
        return self._data.copy()

    def is_tapd_enabled(self) -> bool:
        """检查 TAPD 是否启用"""
        return self._data.get("integrations", {}).get("tapd", {}).get("enabled", False)

    def get_phase(self) -> Optional[str]:
        """获取当前阶段"""
        return self._data.get("phase")

    def get_story_id(self) -> Optional[str]:
        """获取 story_id"""
        return self._data.get("story_id")

    def get_pending_cases(self) -> list[str]:
        """获取未通过验收的 CASE 列表"""
        return [cid for cid, v in self._data.get("verdicts", {}).items() if v != "PASS"]

    def complete_case(self, case_id: str, verdict: str) -> None:
        """标记 CASE 完成（更新 verdict）"""
        self._data["verdicts"][case_id] = verdict
        self._dirty = True

    def all_cases_complete(self) -> bool:
        """检查是否所有 CASE 都已完成（收到 verdict）"""
        verdicts = self._data.get("verdicts", {})
        return all(v in ("PASS", "FAIL") for v in verdicts.values())

    def get_task_id(self) -> Optional[str]:
        """获取 task_id"""
        return self._data.get("task_id")


def emit_event(event_type: str, story_id: str, actor: str, **extra) -> None:
    """追加事件到 events.jsonl"""
    from paths import STATE_DIR
    events_file = STATE_DIR / "events.jsonl"
    events_file.parent.mkdir(parents=True, exist_ok=True)

    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "story_id": story_id,
        "actor": actor,
        **extra
    }

    with events_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def get_recent_events(story_id: str, event_type: Optional[str] = None, limit: int = 20) -> list[dict]:
    """读取最近的事件"""
    from paths import STATE_DIR
    events_file = STATE_DIR / "events.jsonl"
    if not events_file.exists():
        return []

    events = []
    with events_file.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                event = json.loads(line.strip())
                if event.get("story_id") == story_id:
                    if event_type is None or event.get("type") == event_type:
                        events.append(event)
            except json.JSONDecodeError:
                continue

    return events[-limit:]


def check_event(story_id: str, event_type: str) -> bool:
    """检查是否存在指定类型的事件"""
    events = get_recent_events(story_id, event_type, limit=1)
    return len(events) > 0
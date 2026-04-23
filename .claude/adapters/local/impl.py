"""本地适配器实现 - 基于文件系统的适配器"""

import json
import shutil
from pathlib import Path
from typing import Optional, Any


class BaseAdapter:
    """简化版基类"""
    name = "base"
    version = "1.0"
    priority = 0

    def __init__(self):
        self._enabled = self._check_enabled()

    def _check_enabled(self) -> bool:
        return True

    @property
    def enabled(self) -> bool:
        return self._enabled


class LocalAdapter(BaseAdapter):
    """
    本地适配器 - 使用文件系统作为存储

    适用场景：
    - 无 TAPD 账户
    - 离线开发
    - 纯本地工作流
    """

    name = "local"
    version = "1.0"
    priority = 10

    def _check_enabled(self) -> bool:
        """本地适配器始终启用"""
        return True

    def _get_project_root(self) -> Path:
        """获取项目根目录"""
        return Path(__file__).parent.parent.parent.parent

    def _get_consensus_dir(self, story_id: str) -> Path:
        """获取共识目录"""
        return self._get_project_root() / ".chatlabs" / "consensus" / story_id

    def _get_cases_dir(self, case_id: str) -> Path:
        """获取 case 目录"""
        return self._get_project_root() / ".chatlabs" / "cases" / case_id

    def _get_blockers_dir(self, blocker_id: str) -> Path:
        """获取 blocker 目录"""
        return self._get_project_root() / ".chatlabs" / "blockers" / blocker_id

    def _create_event(self, event_type: str, story_id: str, data: dict) -> dict:
        """创建简单事件字典"""
        from datetime import datetime, timezone
        import uuid
        return {
            "schema_version": "1.0",
            "id": str(uuid.uuid4()),
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "source": "local-adapter",
            "story_id": story_id,
            "data": data,
            "meta": {},
        }

    def push_consensus(self, event: dict) -> Optional[dict]:
        """
        推送契约（写入共识状态文件）

        存储结构：
        .chatlabs/consensus/{story_id}/
        ├── contract.md          # 契约文档副本
        ├── status               # 状态文件（pending/approved/rejected）
        └── meta.json            # 元数据
        """
        story_id = event.get("story_id")
        if not story_id:
            return None

        consensus_dir = self._get_consensus_dir(story_id)
        consensus_dir.mkdir(parents=True, exist_ok=True)

        # 写入状态文件
        status_file = consensus_dir / "status"
        status_file.write_text("pending", encoding="utf-8")

        # 复制契约文档（如有）
        contract_path = event.get("data", {}).get("contract_path")
        if contract_path and Path(contract_path).exists():
            shutil.copy(contract_path, consensus_dir / "contract.md")

        # 写入元数据
        meta = {
            "story_id": story_id,
            "contract_version": event.get("data", {}).get("contract_version", "1.0.0"),
            "contract_hash": event.get("data", {}).get("hash", ""),
            "status": "pending",
            "pushed_at": event.get("ts", ""),
            "source": event.get("source", "local-adapter"),
        }
        meta_file = consensus_dir / "meta.json"
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        return self._create_event("local:consensus-pushed", story_id, {
            "consensus_dir": str(consensus_dir),
            "status": "pending",
        })

    def fetch_consensus(self, event: dict) -> Optional[str]:
        """
        获取共识状态

        读取 .chatlabs/consensus/{story_id}/status 文件
        返回：approved / rejected / pending / None
        """
        story_id = event.get("story_id")
        if not story_id:
            return None

        status_file = self._get_consensus_dir(story_id) / "status"
        if not status_file.exists():
            return None

        status = status_file.read_text(encoding="utf-8").strip()
        if status in ("approved", "rejected"):
            return status

        return None

    def emit_subtask(self, event: dict) -> Optional[dict]:
        """
        派发子任务（创建 case 元数据）

        存储结构：
        .chatlabs/cases/{case_id}/
        ├── meta.json            # case 元数据
        └── spec.md              # case 规范副本
        """
        cases = event.get("data", {}).get("cases", [])
        if not cases:
            return None

        story_id = event.get("story_id", "")
        created = []
        for case_id in cases:
            case_dir = self._get_cases_dir(case_id)
            case_dir.mkdir(parents=True, exist_ok=True)

            meta = {
                "case_id": case_id,
                "story_id": story_id,
                "status": "pending",
                "verdict": None,
                "created_at": event.get("ts", ""),
                "source": "local-adapter",
            }
            meta_file = case_dir / "meta.json"
            meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            created.append(case_id)

        return self._create_event("local:subtask-emitted", story_id, {"cases": created})

    def sync_subtask(self, event: dict) -> Optional[dict]:
        """
        同步子任务状态

        更新 .chatlabs/cases/{case_id}/meta.json
        """
        story_id = event.get("story_id", "")
        verdicts = event.get("data", {}).get("verdicts", {})

        updated = []
        for case_id, verdict in verdicts.items():
            case_dir = self._get_cases_dir(case_id)
            meta_file = case_dir / "meta.json"

            if meta_file.exists():
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                meta["verdict"] = verdict
                meta["status"] = "done" if verdict == "PASS" else "failed"
                meta["updated_at"] = event.get("ts", "")
                meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                updated.append(case_id)

        return self._create_event("local:subtask-synced", story_id, {
            "updated": updated,
            "verdicts": verdicts,
        })

    def notify_blocker(self, event: dict) -> Optional[dict]:
        """
        通知阻塞者（写入通知文件）

        存储结构：
        .chatlabs/blockers/{id}/
        ├── notify.json          # 通知内容
        └── meta.json            # 元数据
        """
        blocker_id = event.get("data", {}).get("blocker_id")
        if not blocker_id:
            return None

        story_id = event.get("story_id", "")
        blocker_dir = self._get_blockers_dir(blocker_id)
        blocker_dir.mkdir(parents=True, exist_ok=True)

        notify = {
            "blocker_id": blocker_id,
            "message": event.get("data", {}).get("message", ""),
            "story_id": story_id,
            "created_at": event.get("ts", ""),
        }
        notify_file = blocker_dir / "notify.json"
        notify_file.write_text(json.dumps(notify, ensure_ascii=False, indent=2), encoding="utf-8")

        return self._create_event("local:blocker-notified", story_id, {"blocker_id": blocker_id})

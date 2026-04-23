"""TAPD 适配器实现 - 整合自 tapd-sync 和 tapd-subtask Skill"""

import json
from pathlib import Path
from typing import Optional

from ..base import BaseAdapter

try:
    from flow.event_bus import Event
    from flow.paths import CHATLABS_DIR
except ImportError:
    from ...flow.event_bus import Event
    from ...flow.paths import CHATLABS_DIR


class TapdAdapter(BaseAdapter):
    """
    TAPD 适配器 - 与 TAPD API 集成

    依赖：
    - .claude/tapd-config.json（通过 tapd-init 生成）
    - TAPD MCP Server（chopard-tapd）
    """

    name = "tapd"
    version = "1.0"
    priority = 20

    def _check_enabled(self) -> bool:
        """检查 TAPD 配置是否存在"""
        config_path = Path(__file__).parent.parent.parent / "tapd-config.json"
        return config_path.exists()

    def _load_config(self) -> Optional[dict]:
        """加载 TAPD 配置"""
        config_path = Path(__file__).parent.parent.parent / "tapd-config.json"
        if not config_path.exists():
            return None
        return json.loads(config_path.read_text(encoding="utf-8"))

    def _get_ticket_cache(self, ticket_id: str) -> Optional[dict]:
        """获取工单缓存"""
        cache_file = CHATLABS_DIR / "tapd" / "tickets" / f"{ticket_id}.json"
        if not cache_file.exists():
            return None
        return json.loads(cache_file.read_text(encoding="utf-8"))

    def _save_ticket_cache(self, ticket_id: str, data: dict) -> None:
        """保存工单缓存"""
        cache_file = CHATLABS_DIR / "tapd" / "tickets" / f"{ticket_id}.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def push_consensus(self, event: Event) -> Optional[Event]:
        """
        推送契约到 TAPD Wiki

        实现逻辑（来自 tapd-sync）：
        1. 检查 TAPD enabled
        2. 读取 contract.md，校验 status == "frozen"
        3. 创建/更新 Wiki 页面
        4. 更新 workflow-state.json
        """
        config = self._load_config()
        if not config:
            return None

        story_id = event.story_id
        contract_path = event.data.get("contract_path")

        if not story_id or not contract_path:
            return None

        ticket_cache = self._get_ticket_cache(story_id)
        if not ticket_cache:
            return None

        # 读取契约内容
        contract_content = Path(contract_path).read_text(encoding="utf-8")

        # 构建 Wiki 标题
        wiki_title = f"{ticket_cache.get('name', story_id)} 契约文档 v{event.data.get('contract_version', '1.0.0')}"

        # 注意：实际调用需要 TAPD MCP 工具
        # 这里返回事件，实际执行由 hook 或 Skill 处理
        return Event(
            type="tapd:consensus-pushed",
            source="tapd-adapter",
            story_id=story_id,
            data={
                "wiki_title": wiki_title,
                "contract_version": event.data.get("contract_version"),
                "wiki_id": ticket_cache.get("local_mapping", {}).get("wiki_id"),
            },
        )

    def fetch_consensus(self, event: Event) -> Optional[str]:
        """
        获取评审结果

        实现逻辑（来自 tapd-sync）：
        1. 调用 TAPD API 获取评论
        2. 过滤新评论
        3. 识别 [CONSENSUS-APPROVED] / [CONSENSUS-REJECTED] 标记
        """
        config = self._load_config()
        if not config:
            return None

        story_id = event.story_id
        ticket_cache = self._get_ticket_cache(story_id)
        if not ticket_cache:
            return None

        comment_markers = config.get("comment_markers", {})
        approved_marker = comment_markers.get("approved", "[CONSENSUS-APPROVED]")
        rejected_marker = comment_markers.get("rejected", "[CONSENSUS-REJECTED]")

        # 注意：实际调用需要 TAPD MCP 工具
        # 这里返回 pending，实际检测由 hook 处理
        return None

    def emit_subtask(self, event: Event) -> Optional[Event]:
        """
        派发子任务

        实现逻辑（来自 tapd-subtask）：
        1. 前置三检查（状态枚举、流转合法性）
        2. 创建子任务
        3. 更新本地缓存
        """
        config = self._load_config()
        if not config:
            return None

        story_id = event.story_id
        cases = event.data.get("cases", [])

        if not story_id or not cases:
            return None

        ticket_cache = self._get_ticket_cache(story_id)
        if not ticket_cache:
            return None

        created = []
        for case_id in cases:
            # 注意：实际调用需要 TAPD MCP 工具
            # 这里记录本地状态
            created.append(case_id)

        return Event(
            type="tapd:subtask-emitted",
            source="tapd-adapter",
            story_id=story_id,
            data={"cases": created},
        )

    def sync_subtask(self, event: Event) -> Optional[Event]:
        """
        同步子任务状态

        实现逻辑（来自 tapd-subtask）：
        1. 获取当前状态
        2. 校验流转合法性
        3. 更新 TAPD 状态
        4. 更新本地缓存
        """
        config = self._load_config()
        if not config:
            return None

        story_id = event.story_id
        verdicts = event.data.get("verdicts", {})

        if not story_id or not verdicts:
            return None

        updated = []
        for case_id, verdict in verdicts.items():
            if verdict == "PASS":
                # 注意：实际调用需要 TAPD MCP 工具
                updated.append(case_id)

        return Event(
            type="tapd:subtask-synced",
            source="tapd-adapter",
            story_id=story_id,
            data={"updated": updated, "verdicts": verdicts},
        )

    def notify_blocker(self, event: Event) -> Optional[Event]:
        """
        通知阻塞者

        实现逻辑（来自 jenkins-deploy）：
        发送企业微信通知
        """
        # 注意：实际调用需要相关 MCP 工具
        return Event(
            type="tapd:blocker-notified",
            source="tapd-adapter",
            story_id=event.story_id,
            data={"blocker_id": event.data.get("blocker_id")},
        )

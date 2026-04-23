"""适配器基类"""

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from flow.event_bus import Event


class BaseAdapter(ABC):
    """
    适配器基类

    所有适配器必须实现以下方法：
    - push_consensus: 推送契约到评审渠道
    - fetch_consensus: 获取评审结果
    - emit_subtask: 派发子任务
    - sync_subtask: 同步子任务状态
    - notify_blocker: 通知阻塞者
    """

    name: str = "base"
    version: str = "1.0"
    priority: int = 0

    def __init__(self):
        self._enabled = self._check_enabled()

    def _check_enabled(self) -> bool:
        """检查适配器是否启用"""
        return True

    @property
    def enabled(self) -> bool:
        """适配器是否启用"""
        return self._enabled

    def push_consensus(self, event: "Event") -> Optional["Event"]:
        """
        推送契约到评审渠道

        Args:
            event: contract:frozen 事件

        Returns:
            推送结果事件（如 push-consensus-success）
        """
        raise NotImplementedError

    def fetch_consensus(self, event: "Event") -> Optional[str]:
        """
        获取评审结果

        Args:
            event: 事件对象

        Returns:
            评审结果：approved / rejected / None
        """
        raise NotImplementedError

    def emit_subtask(self, event: "Event") -> Optional["Event"]:
        """
        派发子任务

        Args:
            event: planner:cases-ready 事件

        Returns:
            派发结果事件
        """
        raise NotImplementedError

    def sync_subtask(self, event: "Event") -> Optional["Event"]:
        """
        同步子任务状态

        Args:
            event: generator:all-done 或其他状态变更事件

        Returns:
            同步结果事件
        """
        raise NotImplementedError

    def notify_blocker(self, event: "Event") -> None:
        """
        通知阻塞者

        Args:
            event: blocker 事件
        """
        raise NotImplementedError


class AdapterRegistry:
    """适配器注册表"""

    _adapters: dict[str, type[BaseAdapter]] = {}

    @classmethod
    def register(cls, name: str, adapter_class: type[BaseAdapter]) -> None:
        """注册适配器"""
        cls._adapters[name] = adapter_class

    @classmethod
    def get(cls, name: str) -> Optional[BaseAdapter]:
        """获取适配器实例"""
        adapter_class = cls._adapters.get(name)
        if adapter_class:
            return adapter_class()
        return None

    @classmethod
    def list_adapters(cls) -> list[str]:
        """列出所有注册的适配器"""
        return list(cls._adapters.keys())

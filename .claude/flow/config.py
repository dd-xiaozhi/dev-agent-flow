"""Flow 配置加载器"""

import yaml
from pathlib import Path
from typing import Optional


class FlowConfig:
    """Flow 配置"""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"

        self.config_path = config_path
        self._config = self._load()

    def _load(self) -> dict:
        """加载配置"""
        if not self.config_path.exists():
            return self._default_config()

        with self.config_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _default_config(self) -> dict:
        """默认配置"""
        return {
            "version": "1.0",
            "active_adapters": ["local"],
            "event_aliases": {},
            "phases": {}
        }

    @property
    def active_adapters(self) -> list[str]:
        """获取激活的适配器列表"""
        return self._config.get("active_adapters", [])

    @property
    def event_aliases(self) -> dict:
        """获取事件别名映射"""
        return self._config.get("event_aliases", {})

    @property
    def phases(self) -> dict:
        """获取流程阶段配置"""
        return self._config.get("phases", {})

    def get_phase(self, phase_name: str) -> Optional[dict]:
        """获取指定阶段的配置"""
        return self.phases.get(phase_name)

    def resolve_event_type(self, abstract_event: str, adapter: str) -> str:
        """
        解析事件类型别名

        Args:
            abstract_event: 抽象事件名（如 "consensus:approved"）
            adapter: 适配器名（如 "tapd"、"local"）

        Returns:
            实际事件类型（如 "tapd:consensus-approved"）
        """
        aliases = self.event_aliases.get(abstract_event, {})
        return aliases.get(adapter, abstract_event)

    def get_adapters_for_capability(self, capability: str) -> list[str]:
        """
        获取提供指定能力的适配器列表

        Args:
            capability: 能力名（如 "push-consensus"）

        Returns:
            适配器列表，按优先级排序
        """
        adapters = []
        for adapter_name in self.active_adapters:
            adapter_path = Path(__file__).parent.parent / "adapters" / adapter_name
            adapter_yaml = adapter_path / "adapter.yaml"
            if adapter_yaml.exists():
                with adapter_yaml.open("r", encoding="utf-8") as f:
                    adapter_config = yaml.safe_load(f) or {}
                    provides = adapter_config.get("provides", [])
                    if capability in provides:
                        priority = adapter_config.get("priority", 0)
                        adapters.append((priority, adapter_name))

        # 按优先级排序（数字越大越优先）
        adapters.sort(key=lambda x: x[0], reverse=True)
        return [a[1] for a in adapters]

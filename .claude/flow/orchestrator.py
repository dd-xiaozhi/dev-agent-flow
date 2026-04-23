"""Flow Orchestrator - 核心调度器"""

import importlib.util
from pathlib import Path
from typing import Optional, Callable

from .event_bus import Event, EventBus
from .config import FlowConfig


class FlowOrchestrator:
    """
    流程调度器 - 唯一的流程控制中心

    职责：
    1. 管理事件总线
    2. 根据配置调度组件和适配器
    3. 处理状态流转
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config = FlowConfig(config_path)
        self.event_bus = EventBus()
        self.adapters = self._load_adapters()
        self._event_handlers: list[Callable[[Event], None]] = []

    def _load_adapters(self) -> dict:
        """加载所有激活的适配器"""
        adapters = {}
        for adapter_name in self.config.active_adapters:
            adapter = self._load_adapter(adapter_name)
            if adapter:
                adapters[adapter_name] = adapter
        return adapters

    def _load_adapter(self, adapter_name: str) -> Optional[object]:
        """加载单个适配器"""
        adapter_path = Path(__file__).parent.parent / "adapters" / adapter_name / "impl.py"
        if not adapter_path.exists():
            return None

        spec = importlib.util.spec_from_file_location(f"adapters.{adapter_name}", adapter_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return getattr(module, f"{adapter_name.title().replace('_', '')}Adapter", None)

        return None

    def emit(self, event: Event) -> None:
        """
        发布事件

        Args:
            event: 事件对象
        """
        self.event_bus.append(event)
        self._dispatch_event(event)

    def on_event(self, event: Event) -> None:
        """
        处理外部事件（由 hook 调用）

        Args:
            event: 事件对象
        """
        self.emit(event)

    def register_handler(self, handler: Callable[[Event], None]) -> None:
        """注册事件处理器"""
        self._event_handlers.append(handler)

    def _dispatch_event(self, event: Event) -> None:
        """分发事件到配置中声明的处理器"""
        # 触发注册的处理器
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception:
                pass  # 静默处理处理器异常

        # 检查配置中的 wait_for 规则
        self._check_phase_transition(event)

    def _check_phase_transition(self, event: Event) -> None:
        """检查事件是否触发阶段转换"""
        # 从 workflow-state.json 读取当前 phase
        current_phase = self._get_current_phase()
        if not current_phase:
            return

        phase_config = self.config.get_phase(current_phase)
        if not phase_config:
            return

        wait_for = phase_config.get("wait_for", [])
        for rule in wait_for:
            if self._match_event(rule.get("event", ""), event):
                self._execute_transition(rule, event)
                break

    def _match_event(self, pattern: str, event: Event) -> bool:
        """匹配事件类型"""
        # 支持通配符匹配
        if pattern == "*":
            return True
        if pattern == event.type:
            return True
        # 前缀匹配
        if pattern.endswith("*") and event.type.startswith(pattern[:-1]):
            return True
        return False

    def _execute_transition(self, rule: dict, event: Event) -> None:
        """执行阶段转换"""
        # 1. 运行适配器（如有）
        adapters_to_run = rule.get("adapters", [])
        for adapter_name in adapters_to_run:
            self._run_adapter(adapter_name, event)

        # 2. 更新 phase（如有）
        next_phase = rule.get("next_phase")
        if next_phase:
            self._update_phase(next_phase)

        # 3. 发送消息（如有）
        message = rule.get("message")
        if message:
            self._pending_message = message

    def _run_adapter(self, capability: str, event: Event) -> None:
        """运行提供指定能力的适配器"""
        # 获取提供该能力的适配器
        adapter_names = self.config.get_adapters_for_capability(capability)
        for adapter_name in adapter_names:
            adapter_class = self.adapters.get(adapter_name)
            if adapter_class:
                try:
                    adapter = adapter_class()
                    if hasattr(adapter, capability.replace("-", "_")):
                        method = getattr(adapter, capability.replace("-", "_"))
                        method(event)
                        return  # 成功执行后退出
                except Exception:
                    continue

    def _get_current_phase(self) -> Optional[str]:
        """获取当前 phase"""
        try:
            from ..scripts.workflow_state import WorkflowState
            state = WorkflowState()
            return state.get_phase()
        except Exception:
            return None

    def _update_phase(self, phase: str) -> None:
        """更新 phase"""
        try:
            from ..scripts.workflow_state import WorkflowState
            state = WorkflowState()
            state.update_phase(phase)
        except Exception:
            pass

    def trigger_component(self, component_name: str, story_id: str, **kwargs) -> dict:
        """
        触发组件执行

        Args:
            component_name: 组件名（如 "doc-librarian"）
            story_id: 故事 ID

        Returns:
            组件输出
        """
        # 这里可以扩展为实际调用组件
        # 当前版本主要由 Agent 文档驱动，此方法用于特殊场景
        return {"component": component_name, "story_id": story_id}

    @property
    def pending_message(self) -> Optional[str]:
        """获取待处理的消息"""
        msg = getattr(self, "_pending_message", None)
        if msg:
            self._pending_message = None
        return msg


# 全局单例
_orchestrator: Optional[FlowOrchestrator] = None


def get_orchestrator() -> FlowOrchestrator:
    """获取全局 Flow Orchestrator 实例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = FlowOrchestrator()
    return _orchestrator

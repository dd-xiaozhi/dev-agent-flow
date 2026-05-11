"""Adapter 抽象基类与统一结果数据结构。

任何新 adapter（如未来的 web-playwright）都必须实现 BaseAdapter 接口，
并把结果转换为 AdapterResult，保证 verdict_writer 输出 schema 稳定。
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FailureItem:
    """单条失败的结构化描述。

    所有字段都是可选+默认值，不同 adapter 按需填写；至少要有 reason。
    HTTP adapter 填 endpoint/method/curl；E2E adapter 后续可填 page_url/selector。
    """

    reason: str
    endpoint: str | None = None
    method: str | None = None
    actual: str | None = None
    expected: str | None = None
    curl: str | None = None
    severity: str = "major"  # critical | major | minor


@dataclass
class AdapterResult:
    """adapter 执行结果，由 run.py 序列化为 verdict.json。"""

    verdict: str  # PASS | FAIL | ERROR
    totals: dict[str, int] = field(default_factory=dict)  # passed/failed/errors
    failures: list[FailureItem] = field(default_factory=list)
    raw_log_path: str | None = None
    error_message: str | None = None  # verdict=ERROR 时填基础设施失败原因


class BaseAdapter(abc.ABC):
    """所有 adapter 的统一入口。

    实现要求：
    - 不修改被测系统的代码
    - 不读 generator README/自述（保持验收独立）
    - 把第三方工具的输出归一化成 AdapterResult
    - 失败原因要可复现（HTTP adapter 必须给 curl）
    """

    name: str  # adapter 标识，例如 "http-schemathesis"

    @abc.abstractmethod
    def run(
        self,
        *,
        spec_path: Path,
        base_url: str,
        log_path: Path,
        case_id: str | None = None,
    ) -> AdapterResult:
        """执行验收测试。

        Args:
            spec_path: contract.md 契约文件（doc-librarian 产出）
            base_url: 被测服务 base URL（service_runner 已确认健康）
            log_path: 工具原始日志写入路径
            case_id: 当前 case ID（仅用于日志，不影响测试范围）

        Returns:
            AdapterResult：verdict 必填
        """

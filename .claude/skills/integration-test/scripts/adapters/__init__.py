"""Adapter 注册表：按 stack/adapter 名查 adapter 实现类。

后续新增 adapter 只需：
1. 在本目录新建 my_adapter.py，实现 BaseAdapter
2. 在 _REGISTRY 加一行
"""
from __future__ import annotations

from ._base import AdapterResult, BaseAdapter, FailureItem
from .http_curl import HttpCurlAdapter
from .http_schemathesis import HttpSchemathesisAdapter
from .web_playwright import WebPlaywrightAdapter

_REGISTRY: dict[str, type[BaseAdapter]] = {
    "http-curl": HttpCurlAdapter,                  # 默认 HTTP adapter（显式 curl 用例 + 二元判定）
    "http-schemathesis": HttpSchemathesisAdapter,  # 保留作 fallback：缺 curl-tests.yaml 时降级
    "web-playwright": WebPlaywrightAdapter,        # 前端 E2E adapter（本期 stub）
}


def get_adapter(name: str) -> BaseAdapter:
    """按名取 adapter 实例，未注册抛 KeyError。"""
    cls = _REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"unknown adapter: {name} (registered: {list(_REGISTRY)})")
    return cls()


__all__ = [
    "AdapterResult",
    "BaseAdapter",
    "FailureItem",
    "get_adapter",
]

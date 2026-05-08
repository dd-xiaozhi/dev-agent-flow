"""Adapter 注册表：按 stack/adapter 名查 adapter 实现类。

后续新增 adapter（如 web-playwright）只需：
1. 在本目录新建 my_adapter.py，实现 BaseAdapter
2. 在 _REGISTRY 加一行
"""
from __future__ import annotations

from ._base import AdapterResult, BaseAdapter, FailureItem
from .http_schemathesis import HttpSchemathesisAdapter

_REGISTRY: dict[str, type[BaseAdapter]] = {
    "http-schemathesis": HttpSchemathesisAdapter,
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

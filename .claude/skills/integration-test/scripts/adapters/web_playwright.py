"""Web 前端 E2E adapter（Playwright）—— 本期 stub 占位。

设计意图：保留 adapter 契约（名字、入口签名、verdict 形状），实现留待后续单独 PR。
当前任何调用直接返回 verdict=ERROR(error_message="not implemented")。

future scope（不在本期实现）：
- 读 cases/<case_id>.tests/e2e/*.spec.ts
- 启动 playwright runner（chromium 单浏览器默认）
- 断言通过 playwright expect API，失败明细映射到 FailureItem
"""
from __future__ import annotations

from pathlib import Path

from ._base import AdapterResult, BaseAdapter


class WebPlaywrightAdapter(BaseAdapter):
    """前端 E2E adapter stub —— 后续实现，不在本期范围内。"""

    name = "web-playwright"

    def run(
        self,
        *,
        spec_path: Path,
        base_url: str,
        log_path: Path,
        case_id: str | None = None,
        test_spec_path: Path | None = None,
    ) -> AdapterResult:
        msg = (
            "web-playwright adapter 尚未实现（stub）；前端 E2E 验收将在后续 PR 落地。"
            " 当前请用 http-curl 跑后端契约测试。"
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(msg + "\n", encoding="utf-8")
        return AdapterResult(
            verdict="ERROR",
            error_message=msg,
            raw_log_path=str(log_path),
        )

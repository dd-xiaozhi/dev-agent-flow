"""HTTP 契约测试 adapter：调 uvx schemathesis run 跑契约测试。

依赖：uvx（pip install uv 提供）。schemathesis 通过 uvx 按需拉取。

uvx 调用模板:
    uvx schemathesis run \\
        --base-url=<base_url> \\
        --checks=all \\
        --report=<tmp.json> \\
        <contract_path>

报告解析: schemathesis 不直接输出 JSON 摘要，本 adapter 用 cassette 思路——
通过 stdout 的 "FAILED" 段落 + tap-style 文本提取失败明细。若解析不到，
退化为"看 returncode + 输出末尾摘要"。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ._base import AdapterResult, BaseAdapter, FailureItem


class HttpSchemathesisAdapter(BaseAdapter):
    name = "http-schemathesis"

    # uvx 调用 schemathesis 的总超时（秒），与服务 health check 超时区分
    DEFAULT_TIMEOUT_S = 300

    def run(
        self,
        *,
        spec_path: Path,
        base_url: str,
        log_path: Path,
        case_id: str | None = None,
        test_spec_path: Path | None = None,  # 兼容签名，schemathesis 不使用
    ) -> AdapterResult:
        log_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "uvx",
            "--quiet",
            "schemathesis",
            "run",
            f"--base-url={base_url}",
            "--checks=all",
            "--hypothesis-max-examples=20",
            str(spec_path),
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.DEFAULT_TIMEOUT_S,
            )
        except FileNotFoundError:
            return AdapterResult(
                verdict="ERROR",
                error_message="uvx 未安装，请先 `pip install uv` 或 `brew install uv`",
                raw_log_path=str(log_path),
            )
        except subprocess.TimeoutExpired:
            return AdapterResult(
                verdict="ERROR",
                error_message=f"schemathesis 执行超时（{self.DEFAULT_TIMEOUT_S}s）",
                raw_log_path=str(log_path),
            )

        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        log_path.write_text(combined, encoding="utf-8")

        totals = self._parse_totals(combined)
        failures = self._parse_failures(combined)

        # schemathesis: returncode 0=全过；非 0=有失败或错误
        if proc.returncode == 0 and not failures:
            verdict = "PASS"
        elif proc.returncode != 0 and not failures and totals.get("failed", 0) == 0:
            # 没解析出明细但 returncode 非 0，归为 ERROR
            verdict = "ERROR"
            return AdapterResult(
                verdict=verdict,
                totals=totals,
                failures=[],
                raw_log_path=str(log_path),
                error_message=f"schemathesis exited {proc.returncode} 但未解析出失败明细，请看原始日志",
            )
        else:
            verdict = "FAIL"

        return AdapterResult(
            verdict=verdict,
            totals=totals,
            failures=failures,
            raw_log_path=str(log_path),
        )

    @staticmethod
    def _parse_totals(text: str) -> dict[str, int]:
        """从 schemathesis 末尾摘要提取 passed/failed/errors 计数。

        典型输出: `=== 12 passed, 3 failed in 4.2s ===`
        """
        totals = {"passed": 0, "failed": 0, "errors": 0}
        m = re.search(r"=+\s*(.+?)\s*=+\s*$", text.strip(), re.MULTILINE)
        if not m:
            return totals
        summary = m.group(1)
        for key in ("passed", "failed", "errors"):
            mm = re.search(rf"(\d+)\s+{key}", summary)
            if mm:
                totals[key] = int(mm.group(1))
        return totals

    @staticmethod
    def _parse_failures(text: str) -> list[FailureItem]:
        """提取失败明细，schemathesis 默认输出包含 endpoint/method/curl 段。

        匹配模式（示例）:
            FAILED: GET /api/users
            ...
            Run this Python code to reproduce this failure:
              requests.get('http://...')
            ...
        """
        failures: list[FailureItem] = []
        # 粗匹配：每个 "FAILED: <METHOD> <PATH>" 段
        for m in re.finditer(
            r"FAILED:\s*(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(\S+)\s*\n(.*?)(?=\n(?:FAILED:|=+\s|\Z))",
            text,
            re.DOTALL,
        ):
            method = m.group(1)
            endpoint = m.group(2)
            body = m.group(3)
            # 提取 reason：取段落第一个非空行
            reason_match = re.search(r"^\s*(\S.+?)$", body, re.MULTILINE)
            reason = reason_match.group(1).strip() if reason_match else "schemathesis check failed"
            # 尝试提取 curl
            curl_match = re.search(
                r"(curl\s+-X\s+\w+[^\n]+)", body
            )
            curl = curl_match.group(1).strip() if curl_match else None

            failures.append(
                FailureItem(
                    reason=reason[:500],
                    endpoint=endpoint,
                    method=method,
                    curl=curl,
                    severity="major",
                )
            )
        return failures

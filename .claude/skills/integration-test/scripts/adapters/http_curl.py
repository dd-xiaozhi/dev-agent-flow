"""HTTP 显式用例 adapter：跑 curl-tests.yaml 中按 AC 编排的请求并断言响应。

设计要点（与 schemathesis 黑盒模糊不同）：
- planner 拆 case 时同步产出 `<case_id>.tests.yaml`，每条 AC 至少 1 个用例
- 本 adapter 用 `requests` 库发请求（稳定、易超时），并为每条失败用例渲染等价 curl
- 断言能力刻意收窄：只支持 status + json 字段（等值 / {exists, type}）
- 顺序依赖：capture（响应字段进 context）+ depends_on（显式串）

调用上下游：
- run.py 决定是否走 http-curl（见 yaml 是否存在），yaml 路径通过 test_spec_path 传入
- 失败明细写入 AdapterResult.failures（含 curl 字段，generator 直接可复现）
"""
from __future__ import annotations

import json
import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ._base import AdapterResult, BaseAdapter, FailureItem

# 依赖按需 import，缺失时 verdict=ERROR（早返 + 明确提示）
try:
    import requests  # type: ignore
    import yaml  # type: ignore
    from jsonpath_ng import parse as jsonpath_parse  # type: ignore
except ImportError as e:  # pragma: no cover
    _IMPORT_ERROR: str | None = (
        f"http-curl adapter 缺依赖 ({e.name})；请在执行环境安装："
        f" `uv pip install requests pyyaml jsonpath-ng`"
    )
    requests = None  # type: ignore
    yaml = None  # type: ignore
    jsonpath_parse = None  # type: ignore
else:
    _IMPORT_ERROR = None


REQUEST_TIMEOUT_S = 10
VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass
class _TestCase:
    """单条用例的解析后形态（schema 校验后的安全视图）。"""

    name: str
    ac: str
    method: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    query: dict[str, Any] = field(default_factory=dict)
    body: Any = None
    expect_status: int | None = None
    expect_json: dict[str, Any] = field(default_factory=dict)
    capture: dict[str, str] = field(default_factory=dict)
    depends_on: str | None = None


class HttpCurlAdapter(BaseAdapter):
    """跑 curl-tests.yaml 的二元判定 adapter。"""

    name = "http-curl"

    def run(
        self,
        *,
        spec_path: Path,
        base_url: str,
        log_path: Path,
        case_id: str | None = None,
        test_spec_path: Path | None = None,
    ) -> AdapterResult:
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if _IMPORT_ERROR:
            log_path.write_text(_IMPORT_ERROR + "\n", encoding="utf-8")
            return AdapterResult(
                verdict="ERROR",
                error_message=_IMPORT_ERROR,
                raw_log_path=str(log_path),
            )

        if test_spec_path is None or not test_spec_path.exists():
            msg = f"http-curl 需要 curl-tests.yaml，但未提供或文件不存在: {test_spec_path}"
            log_path.write_text(msg + "\n", encoding="utf-8")
            return AdapterResult(
                verdict="ERROR",
                error_message=msg,
                raw_log_path=str(log_path),
            )

        # 1. 加载 yaml + schema 校验
        try:
            raw = yaml.safe_load(test_spec_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            msg = f"yaml 解析失败: {e}"
            log_path.write_text(msg + "\n", encoding="utf-8")
            return AdapterResult(
                verdict="ERROR", error_message=msg, raw_log_path=str(log_path)
            )

        try:
            tests, yaml_base_url, defaults = _parse_yaml(raw)
        except _SchemaError as e:
            log_path.write_text(str(e) + "\n", encoding="utf-8")
            return AdapterResult(
                verdict="ERROR", error_message=str(e), raw_log_path=str(log_path)
            )

        # base_url 优先级：service_runner 注入的实际地址 > yaml 中的 ${BASE_URL} 解析
        # yaml 里通常写 ${BASE_URL}，由本步骤替换为 service_runner 给出的 base_url
        effective_base_url = _render_vars(yaml_base_url or "${BASE_URL}", {"BASE_URL": base_url})

        # 2. 执行（按 yaml 顺序，depends_on 跳过失败下游）
        context: dict[str, str] = {}
        failed_names: set[str] = set()
        passed = 0
        failed = 0
        errors = 0
        skipped = 0
        failures: list[FailureItem] = []
        log_lines: list[str] = []

        for tc in tests:
            # 依赖跳过
            if tc.depends_on and tc.depends_on in failed_names:
                skipped += 1
                errors += 1  # 计入 errors 槽位（依赖失败 = 测试体系问题）
                log_lines.append(f"[SKIP] {tc.name} (depends_on {tc.depends_on} failed)")
                continue

            try:
                resp = _do_request(tc, effective_base_url, defaults, context)
            except requests.ConnectionError as e:
                msg = f"连接失败（被测服务可能未就绪）: {e}"
                log_lines.append(f"[ERROR] {tc.name}: {msg}")
                log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
                return AdapterResult(
                    verdict="ERROR",
                    totals={"passed": passed, "failed": failed, "errors": errors + 1, "skipped": skipped},
                    failures=failures,
                    raw_log_path=str(log_path),
                    error_message=msg,
                )
            except requests.Timeout:
                msg = f"请求超时 ({REQUEST_TIMEOUT_S}s)"
                log_lines.append(f"[ERROR] {tc.name}: {msg}")
                failed_names.add(tc.name)
                failures.append(
                    FailureItem(
                        reason=msg,
                        endpoint=tc.path,
                        method=tc.method,
                        curl=_render_curl(tc, effective_base_url, defaults, context),
                        severity="major",
                    )
                )
                failed += 1
                continue

            ok, reason, actual_repr, expected_repr = _assert_response(tc, resp)
            if ok:
                passed += 1
                log_lines.append(f"[PASS] {tc.name} ({resp.status_code})")
                # 捕获 capture 字段进 context
                for var, jp in tc.capture.items():
                    try:
                        body_json = resp.json()
                        matches = jsonpath_parse(jp).find(body_json)
                        if matches:
                            context[var] = str(matches[0].value)
                    except (ValueError, json.JSONDecodeError):
                        pass  # capture 失败不阻断，下游若需要会以 ${VAR} 字面量触发显式错误
            else:
                failed += 1
                failed_names.add(tc.name)
                log_lines.append(f"[FAIL] {tc.name}: {reason}")
                failures.append(
                    FailureItem(
                        reason=reason,
                        endpoint=tc.path,
                        method=tc.method,
                        actual=actual_repr[:500] if actual_repr else None,
                        expected=expected_repr[:500] if expected_repr else None,
                        curl=_render_curl(tc, effective_base_url, defaults, context),
                        severity="major",
                    )
                )

        log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

        totals = {"passed": passed, "failed": failed, "errors": errors, "skipped": skipped}
        if failed == 0 and errors == 0:
            verdict = "PASS"
        elif failed > 0:
            verdict = "FAIL"
        else:
            verdict = "ERROR"

        return AdapterResult(
            verdict=verdict,
            totals=totals,
            failures=failures,
            raw_log_path=str(log_path),
        )


# ── yaml schema 校验 ─────────────────────────────────────────────────


class _SchemaError(Exception):
    """yaml 结构不符合契约。"""


def _parse_yaml(raw: Any) -> tuple[list[_TestCase], str, dict[str, Any]]:
    """把 yaml dict 转换为 _TestCase 列表 + base_url + defaults。"""
    if not isinstance(raw, dict):
        raise _SchemaError("yaml 顶层必须是 mapping")

    yaml_base_url = raw.get("base_url", "${BASE_URL}")
    defaults = raw.get("defaults", {}) or {}
    if not isinstance(defaults, dict):
        raise _SchemaError("defaults 必须是 mapping")

    tests_raw = raw.get("tests")
    if not isinstance(tests_raw, list) or not tests_raw:
        raise _SchemaError("tests 必须是非空数组")

    tests: list[_TestCase] = []
    for i, t in enumerate(tests_raw):
        if not isinstance(t, dict):
            raise _SchemaError(f"tests[{i}] 必须是 mapping")
        name = t.get("name")
        ac = t.get("ac")
        if not name or not ac:
            raise _SchemaError(f"tests[{i}] 缺 name 或 ac")
        req = t.get("request")
        if not isinstance(req, dict):
            raise _SchemaError(f"tests[{i}].request 必须是 mapping")
        method = (req.get("method") or "").upper()
        path = req.get("path")
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
            raise _SchemaError(f"tests[{i}].request.method 非法: {method}")
        if not path or not isinstance(path, str):
            raise _SchemaError(f"tests[{i}].request.path 必须是字符串")

        expect = t.get("expect") or {}
        if not isinstance(expect, dict):
            raise _SchemaError(f"tests[{i}].expect 必须是 mapping")
        expect_status = expect.get("status")
        if expect_status is not None and not isinstance(expect_status, int):
            raise _SchemaError(f"tests[{i}].expect.status 必须是整数")
        expect_json = expect.get("json") or {}
        if not isinstance(expect_json, dict):
            raise _SchemaError(f"tests[{i}].expect.json 必须是 mapping")

        tests.append(
            _TestCase(
                name=str(name),
                ac=str(ac),
                method=method,
                path=path,
                headers=req.get("headers") or {},
                query=req.get("query") or {},
                body=req.get("body"),
                expect_status=expect_status,
                expect_json=expect_json,
                capture=t.get("capture") or {},
                depends_on=t.get("depends_on"),
            )
        )
    return tests, yaml_base_url, defaults


# ── 变量替换 ────────────────────────────────────────────────────────


def _render_vars(text: str, context: dict[str, str]) -> str:
    """把 ${VAR} 替换为 context 或环境变量值，未定义保留原样。"""
    def _sub(m: re.Match[str]) -> str:
        var = m.group(1)
        if var in context:
            return context[var]
        return os.environ.get(var, m.group(0))
    return VAR_RE.sub(_sub, text)


def _render_obj(obj: Any, context: dict[str, str]) -> Any:
    """递归渲染 dict/list/str 中的 ${VAR}。"""
    if isinstance(obj, str):
        return _render_vars(obj, context)
    if isinstance(obj, dict):
        return {k: _render_obj(v, context) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_render_obj(v, context) for v in obj]
    return obj


# ── 请求执行 ───────────────────────────────────────────────────────


def _do_request(
    tc: _TestCase,
    base_url: str,
    defaults: dict[str, Any],
    context: dict[str, str],
) -> requests.Response:  # type: ignore[name-defined]
    """发请求；连接/超时异常向上抛，由 run() 决定终止 vs 单条失败。"""
    url = base_url.rstrip("/") + _render_vars(tc.path, context)
    headers = {**(defaults.get("headers") or {}), **tc.headers}
    headers = _render_obj(headers, context)
    body = _render_obj(tc.body, context) if tc.body is not None else None
    params = _render_obj(tc.query, context) if tc.query else None

    return requests.request(
        method=tc.method,
        url=url,
        headers=headers,
        params=params,
        json=body if body is not None else None,
        timeout=REQUEST_TIMEOUT_S,
    )


# ── 响应断言 ───────────────────────────────────────────────────────


def _assert_response(
    tc: _TestCase, resp: requests.Response  # type: ignore[name-defined]
) -> tuple[bool, str, str | None, str | None]:
    """返回 (ok, reason, actual_repr, expected_repr)。"""
    # status 断言
    if tc.expect_status is not None and resp.status_code != tc.expect_status:
        body_text = resp.text[:500] if resp.text else ""
        return (
            False,
            f"status mismatch: actual={resp.status_code} expected={tc.expect_status}",
            f"HTTP {resp.status_code} body={body_text}",
            f"HTTP {tc.expect_status}",
        )

    # json 断言（每条都要过）
    if tc.expect_json:
        try:
            body_json = resp.json()
        except (ValueError, json.JSONDecodeError):
            return (
                False,
                "response is not JSON but expect.json is set",
                resp.text[:500],
                json.dumps(tc.expect_json, ensure_ascii=False),
            )
        for jp, expected in tc.expect_json.items():
            matches = jsonpath_parse(jp).find(body_json)
            actual_value = matches[0].value if matches else None
            ok, reason = _check_json_clause(jp, actual_value, expected, matches)
            if not ok:
                return (
                    False,
                    reason,
                    json.dumps(body_json, ensure_ascii=False)[:500],
                    f"{jp} = {expected}",
                )
    return True, "", None, None


def _check_json_clause(
    jp: str, actual: Any, expected: Any, matches: list
) -> tuple[bool, str]:
    """单条 json 断言：支持等值 / {exists: bool} / {type: str}。"""
    if isinstance(expected, dict) and ("exists" in expected or "type" in expected):
        if expected.get("exists") is True and not matches:
            return False, f"jsonpath {jp} not found"
        if expected.get("exists") is False and matches:
            return False, f"jsonpath {jp} should not exist but found"
        type_name = expected.get("type")
        if type_name:
            if not matches:
                return False, f"jsonpath {jp} not found (cannot check type)"
            type_map = {
                "string": str,
                "int": int,
                "integer": int,
                "number": (int, float),
                "float": float,
                "bool": bool,
                "boolean": bool,
                "list": list,
                "array": list,
                "dict": dict,
                "object": dict,
            }
            expected_py = type_map.get(type_name)
            if expected_py is None:
                return False, f"unknown type assertion: {type_name}"
            if not isinstance(actual, expected_py):
                return (
                    False,
                    f"jsonpath {jp} type mismatch: actual={type(actual).__name__} expected={type_name}",
                )
        return True, ""
    # 等值比较
    if actual != expected:
        return False, f"jsonpath {jp} mismatch: actual={actual!r} expected={expected!r}"
    return True, ""


# ── curl 命令渲染（用于 FailureItem.curl，generator 复现用） ──────────


def _render_curl(
    tc: _TestCase,
    base_url: str,
    defaults: dict[str, Any],
    context: dict[str, str],
) -> str:
    """生成等价 curl 命令字符串。"""
    url = base_url.rstrip("/") + _render_vars(tc.path, context)
    headers = {**(defaults.get("headers") or {}), **tc.headers}
    headers = _render_obj(headers, context)
    body = _render_obj(tc.body, context) if tc.body is not None else None

    parts = ["curl", "-X", tc.method, shlex.quote(url)]
    for k, v in headers.items():
        parts += ["-H", shlex.quote(f"{k}: {v}")]
    if body is not None:
        body_str = json.dumps(body, ensure_ascii=False) if not isinstance(body, str) else body
        parts += ["-d", shlex.quote(body_str)]
    return " ".join(parts)

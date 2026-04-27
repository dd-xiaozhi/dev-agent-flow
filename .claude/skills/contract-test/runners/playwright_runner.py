#!/usr/bin/env python3
"""
playwright runner — E2E 端到端测试
支持前端页面行为验证，与 OpenAPI 契约测试互补
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def _service_reachable(url: str, timeout: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return False


def _find_playwright_config(project_root: Path) -> Path | None:
    """查找 playwright.config.{ts,js,mjs,cjs}"""
    for name in ["playwright.config.ts", "playwright.config.js",
                 "playwright.config.mjs", "playwright.config.cjs"]:
        p = project_root / name
        if p.is_file():
            return p
    return None


def _find_package_json(project_root: Path) -> Path | None:
    """查找最近的 package.json"""
    for pattern in [
        project_root / "package.json",
        *project_root.glob("packages/*/package.json"),
        *project_root.glob("apps/*/package.json"),
    ]:
        if pattern.is_file():
            return pattern
    return None


def _run_npm_command(cmd: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def run(openapi: str, base_url: str, output: str) -> int:
    openapi_path = Path(openapi)
    project_root = _find_project_root(openapi_path)
    pkg_json = _find_package_json(project_root)

    if not pkg_json:
        return _write_error(
            output,
            "未找到 package.json，无法运行 Playwright 测试",
            "确认项目根目录正确，或添加 package.json",
        )

    node_modules_dir = pkg_json.parent / "node_modules"
    if not node_modules_dir.is_dir():
        print("[playwright] node_modules 未安装，尝试安装...", file=sys.stderr)
        code, _, _ = _run_npm_command(["npm", "install", "--prefer-offline"], cwd=pkg_json.parent, timeout=300)
        if code != 0:
            return _write_error(output, "npm install 失败", "手动执行 npm install")

    playwright_ok = (node_modules_dir / "playwright").is_dir() or (node_modules_dir / "@playwright").is_dir()
    if not playwright_ok:
        print("[playwright] 安装 Playwright...", file=sys.stderr)
        code, _, _ = _run_npm_command(
            ["npm", "install", "-D", "@playwright/test"], cwd=pkg_json.parent, timeout=300
        )
        if code != 0:
            return _write_error(output, "Playwright 安装失败", "手动执行: npm install -D @playwright/test")
        _run_npm_command(
            ["npx", "playwright", "install", "--with-deps"], cwd=pkg_json.parent, timeout=600
        )

    if base_url and base_url != "http://localhost:3000":
        import os
        os.environ["TEST_BASE_URL"] = base_url

    print(f"[playwright] project_root={pkg_json.parent} base-url={base_url}")

    config = _find_playwright_config(pkg_json.parent)
    cmd = ["npx", "playwright", "test"]
    if config:
        cmd.extend(["--config", str(config)])

    code, stdout, stderr = _run_npm_command(cmd, cwd=pkg_json.parent, timeout=300)
    combined = stdout + "\n" + stderr
    passed, failed, skipped = _parse_output(combined)
    verdict = "PASS" if (code == 0 and failed == 0) else "FAIL"

    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "contract-test",
        "runner": "playwright",
        "verdict": verdict,
        "openapi": openapi,
        "base_url": base_url,
        "project_root": str(pkg_json.parent),
        "test_count": passed + failed + skipped,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "failures": _extract_failures(combined),
        "contract_violations": [],
        "next_action": "交付" if verdict == "PASS" else "修复失败测试后重跑",
    }
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[playwright] verdict={verdict} passed={passed} failed={failed}")
    return 0 if verdict == "PASS" else 1


def _parse_output(output: str) -> tuple[int, int, int]:
    passed = failed = skipped = 0
    lines = [ln for ln in output.splitlines() if "passed" in ln or "failed" in ln]
    if not lines:
        return 0, 0, 0
    text = lines[-1]
    m = re.search(r"(\d+)\s+passed", text)
    if m: passed = int(m.group(1))
    m = re.search(r"(\d+)\s+failed", text)
    if m: failed = int(m.group(1))
    m = re.search(r"(\d+)\s+skipped", text)
    if m: skipped = int(m.group(1))
    return passed, failed, skipped


def _extract_failures(output: str) -> list[dict]:
    failures = []
    blocks = re.split(r"\n\s*\d+\)\s+\[", output)
    for block in blocks[1:]:
        lines = block.splitlines()
        if not lines:
            continue
        name = lines[0].rsplit("]", 1)[-1].strip() if "]" in lines[0] else lines[0].strip()
        err_lines = [ln for ln in lines[1:4] if ln.strip()]
        failures.append({
            "test": name,
            "error": " | ".join(err_lines),
            "fix": "检查页面元素或网络请求是否符合预期",
        })
    return failures[:10]


def _find_project_root(openapi_path: Path) -> Path:
    cur = openapi_path.resolve().parent
    markers = ["package.json", "pom.xml", "requirements.txt", "pyproject.toml"]
    while cur != cur.parent:
        if any((cur / m).is_file() for m in markers):
            return cur
        cur = cur.parent
    return openapi_path.resolve().parent


def _write_error(output: str, message: str, fix: str) -> int:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "contract-test",
        "runner": "playwright",
        "verdict": "ERROR",
        "test_count": 0, "passed": 0, "failed": 0,
        "failures": [{"error": message, "fix": fix}],
        "contract_violations": [],
        "next_action": "修复配置后重试",
    }
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ERROR: {message}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="playwright E2E runner")
    ap.add_argument("--openapi", required=False, default="")
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    sys.exit(run(args.openapi, args.base_url, args.output))

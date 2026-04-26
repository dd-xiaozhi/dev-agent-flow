#!/usr/bin/env python3
"""
schemathesis adapter — Python / FastAPI 契约测试 runner
依据：skills/contract-test/SKILL.md；examples/hello-python/ 配套

对外接口：
  CLI:   python schemathesis_runner.py --openapi <ignored> --base-url <url> --output <path>
  模块:  run(openapi: str, base_url: str, output: str) -> int
"""
from __future__ import annotations

import argparse
import json
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


def run(openapi: str, base_url: str, output: str) -> int:
    openapi_endpoint = f"{base_url.rstrip('/')}/openapi.json"

    if not _service_reachable(openapi_endpoint):
        print(f"ERROR: 服务不可达: {openapi_endpoint}", file=sys.stderr)
        return 2

    print(f"[schemathesis] base-url={base_url} openapi={openapi_endpoint}")

    proc = subprocess.run(
        ["schemathesis", "run", openapi_endpoint, "--verbose", "--exitcode-ci"],
        capture_output=True,
        text=True,
    )
    schemathesis_exit = proc.returncode
    output_text = proc.stdout + proc.stderr

    # 对齐原脚本：按含 PASS/FAIL 的行数粗略计数（heuristic）
    passed = sum(1 for ln in output_text.splitlines() if "PASS" in ln)
    failed = sum(1 for ln in output_text.splitlines() if "FAIL" in ln)
    verdict = "PASS" if schemathesis_exit == 0 else "FAIL"

    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "contract-test",
        "adapter": "schemathesis",
        "verdict": verdict,
        "openapi_endpoint": openapi_endpoint,
        "base_url": base_url,
        "test_count": passed + failed,
        "passed": passed,
        "failed": failed,
        "raw_output": "\n".join(output_text.splitlines()[:50]),
        "failures": [],
        "contract_violations": [],
        "next_action": "交付" if schemathesis_exit == 0 else "修复后重跑",
    }
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[schemathesis] verdict={verdict} passed={passed} failed={failed}")
    print(f"verdict saved: {output}")
    return schemathesis_exit


def _main() -> int:
    ap = argparse.ArgumentParser(description="schemathesis contract-test runner")
    ap.add_argument("--openapi", required=False, default="")
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--output", required=True)
    args, _ = ap.parse_known_args()
    return run(args.openapi, args.base_url, args.output)


if __name__ == "__main__":
    sys.exit(_main())

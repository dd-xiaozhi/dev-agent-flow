#!/usr/bin/env python3
"""
rest-assured adapter — Java / SpringBoot 契约测试 runner
依据：skills/contract-test/SKILL.md；examples/hello-java/ 配套

对外接口：
  CLI:   python rest_assured_runner.py --openapi <path> --base-url <url> --output <path>
  模块:  run(openapi: str, base_url: str, output: str) -> int
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _find_maven_root(openapi_path: Path) -> Path | None:
    """从 openapi 文件所在目录向上找 pom.xml"""
    cur = openapi_path.resolve().parent
    while cur != cur.parent:
        if (cur / "pom.xml").is_file():
            return cur
        cur = cur.parent
    return None


def _parse_surefire(reports_dir: Path) -> tuple[int, int]:
    """解析 surefire-reports/*.txt，返回 (passed, failed)"""
    passed = failed = 0
    if not reports_dir.is_dir():
        return passed, failed
    pat = re.compile(
        r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)"
    )
    for txt in reports_dir.glob("*.txt"):
        try:
            content = txt.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in pat.finditer(content):
            total, fails, errs, skipped = (int(x) for x in m.groups())
            failed += fails + errs
            passed += total - fails - errs - skipped
    return passed, failed


def run(openapi: str, base_url: str, output: str) -> int:
    openapi_path = Path(openapi)
    maven_dir = _find_maven_root(openapi_path)
    if not maven_dir:
        print("ERROR: 找不到 pom.xml（Maven 项目）", file=sys.stderr)
        return 2

    print(f"[rest-assured] project={maven_dir} base-url={base_url}")

    proc = subprocess.run(
        [
            "mvn", "test",
            "-Dtest=ContractTest",
            f"-DbaseUrl={base_url}",
            "-DfailIfNoTests=false",
            "-q",
        ],
        cwd=str(maven_dir),
        capture_output=True,
        text=True,
    )
    # 打印 Maven 输出末尾 5 行（对齐原脚本 `tail -5` 行为）
    tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-5:])
    if tail:
        print(tail)

    test_exit = proc.returncode
    passed, failed = _parse_surefire(maven_dir / "target" / "surefire-reports")
    verdict = "PASS" if test_exit == 0 else "FAIL"

    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "contract-test",
        "adapter": "rest-assured",
        "verdict": verdict,
        "openapi": openapi,
        "base_url": base_url,
        "test_count": passed + failed,
        "passed": passed,
        "failed": failed,
        "failures": [],
        "contract_violations": [],
        "next_action": "交付" if test_exit == 0 else "修复后重跑",
    }
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[rest-assured] verdict={verdict} passed={passed} failed={failed}")
    print(f"verdict saved: {output}")
    return test_exit


def _main() -> int:
    ap = argparse.ArgumentParser(description="rest-assured contract-test runner")
    ap.add_argument("--openapi", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--output", required=True)
    args, _ = ap.parse_known_args()
    return run(args.openapi, args.base_url, args.output)


if __name__ == "__main__":
    sys.exit(_main())

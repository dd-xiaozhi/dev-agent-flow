#!/usr/bin/env python3
"""
openapi runner — HTTP API Schema 验证
基于 schemathesis（Python）或 rest-assured（Java）
统一接口，屏蔽底层差异
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# 动态引入同目录的 adapters（向后兼容）
_SCRIPT_DIR = Path(__file__).resolve().parent
_ADAPTERS_DIR = _SCRIPT_DIR.parent / "adapters"
if str(_ADAPTERS_DIR) not in sys.path:
    sys.path.insert(0, str(_ADAPTERS_DIR))


def detect_backend_stack(project_root: Path) -> str:
    """推断后端技术栈，返回 adapter 名"""
    if (project_root / "pom.xml").is_file():
        return "rest-assured"
    if any((project_root / f).is_file() for f in ("requirements.txt", "pyproject.toml", "setup.py")):
        return "schemathesis"
    if (project_root / "go.mod").is_file():
        return "schemathesis"  # Go 生态暂无专属 runner，借用 schemathesis
    return "schemathesis"  # 默认


def run(openapi: str, base_url: str, output: str) -> int:
    """
    入口：自动检测后端技术栈，执行对应 adapter
    """
    import json
    from datetime import datetime, timezone

    openapi_path = Path(openapi)
    project_root = _find_project_root(openapi_path)
    adapter = detect_backend_stack(project_root)

    # 导入并调用对应 adapter
    try:
        if adapter == "rest-assured":
            from adapters import rest_assured_runner as runner_mod
        else:
            from adapters import schemathesis_runner as runner_mod
    except ImportError as e:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": "contract-test",
            "runner": "openapi",
            "verdict": "ERROR",
            "openapi": openapi,
            "base_url": base_url,
            "test_count": 0,
            "passed": 0,
            "failed": 0,
            "failures": [{"error": f"adapter '{adapter}' 加载失败: {e}", "fix": "确认 adapter 依赖已安装"}],
            "contract_violations": [],
            "next_action": "安装依赖后重试",
        }
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    print(f"[openapi runner] adapter={adapter} openapi={openapi} base-url={base_url}")
    return runner_mod.run(openapi, base_url, output)


def _find_project_root(openapi_path: Path) -> Path:
    """向上查找项目根目录"""
    cur = openapi_path.resolve().parent
    markers = [
        "pom.xml", "requirements.txt", "pyproject.toml", "setup.py",
        "go.mod", "Cargo.toml", "package.json",
    ]
    while cur != cur.parent:
        if any((cur / m).is_file() for m in markers):
            return cur
        cur = cur.parent
    return openapi_path.resolve().parent


# ─── CLI ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="openapi runner")
    ap.add_argument("--openapi", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    sys.exit(run(args.openapi, args.base_url, args.output))

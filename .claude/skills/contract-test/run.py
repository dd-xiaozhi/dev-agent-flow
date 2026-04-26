#!/usr/bin/env python3
"""
contract-test 统一入口
依据：skills/contract-test/SKILL.md §4（适配器插件架构）

用法：
  python run.py --openapi <path> --base-url <url> [--adapter <name>] [--output <path>]

选项：
  --openapi   OpenAPI spec 路径（必需）
  --base-url  被测服务 base URL（必需）
  --adapter   rest-assured | schemathesis（不指定则自动推断）
  --output    verdict 输出路径（默认 ${OUTPUT_DIR:-./reports/verdicts}/<ts>.json）

退出码：adapter 的退出码；参数/adapter 加载失败为 2
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ADAPTERS_DIR = SCRIPT_DIR / "adapters"
# adapter CLI 名（用 "-"） ↔ Python 模块名（用 "_"）
ADAPTER_MODULES = {
    "rest-assured": "rest_assured_runner",
    "schemathesis": "schemathesis_runner",
}


def _detect_adapter(openapi: Path) -> str | None:
    """按 openapi 内容与同级项目文件推断 adapter"""
    try:
        content = openapi.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        content = ""

    if any(k in content for k in ("rest-assured", "spring-boot", "junit")):
        return "rest-assured"
    if any(k in content for k in ("fastapi", "python")):
        return "schemathesis"

    parent = openapi.resolve().parent
    if (parent / "pom.xml").is_file():
        return "rest-assured"
    if (parent / "requirements.txt").is_file():
        return "schemathesis"
    return None


def _load_adapter(name: str):
    """动态 import adapter 模块"""
    module_name = ADAPTER_MODULES.get(name)
    if not module_name:
        return None
    # 确保 adapters/ 可被 import
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    try:
        return importlib.import_module(f"adapters.{module_name}")
    except ImportError as e:
        print(f"ERROR: 加载 adapter '{name}' 失败: {e}", file=sys.stderr)
        return None


def main() -> int:
    ap = argparse.ArgumentParser(
        description="contract-test 统一入口", add_help=True
    )
    ap.add_argument("--openapi", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--output", default=None)
    args = ap.parse_args()

    openapi = Path(args.openapi)
    output_dir = Path(os.environ.get("OUTPUT_DIR") or "./reports/verdicts")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output or str(
        output_dir / f"{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    )

    adapter = args.adapter or _detect_adapter(openapi)
    if not adapter:
        print("ERROR: 无法推断 adapter，请显式指定 --adapter", file=sys.stderr)
        return 2

    module = _load_adapter(adapter)
    if not module:
        print(
            f"ERROR: adapter '{adapter}' 未找到。可用：{', '.join(ADAPTER_MODULES)}",
            file=sys.stderr,
        )
        return 2

    return module.run(str(openapi), args.base_url, output)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
contract-test 统一入口 — 智能策略路由
依据：skills/contract-test/SKILL.md

职责：
  1. 检测项目类型（backend-only | frontend-backend | spa | microservices）
  2. 根据项目类型自动选择 runner（可手动覆盖）
  3. 收集多个 runner 的 verdict，汇总为最终报告

用法：
  python run.py --openapi <path> --base-url <url> [--runner openapi|playwright|all>] [--output <path>]
  python run.py --detect-only   # 仅检测项目类型，不运行测试

退出码：
  0  = 所有 runner PASS
  1  = 任意 runner FAIL
  2  = 参数错误 / runner 加载失败
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parents[2]
sys.path.insert(0, str(PROJECT_DIR / ".claude" / "scripts"))
sys.path.insert(0, str(SCRIPT_DIR))

from paths import REPORTS_DIR

RUNNERS_DIR = SCRIPT_DIR / "runners"
DETECTORS_DIR = SCRIPT_DIR / "detectors"

# runner CLI 名 ↔ Python 模块名
RUNNER_MODULES = {
    "openapi":   "openapi_runner",
    "playwright": "playwright_runner",
}


def detect_project_type(project_root: Path | None = None) -> str:
    """动态导入 detectors，避免循环依赖"""
    try:
        from detectors.project_type import detect_project_type as _detect
        return _detect(project_root)
    except ImportError:
        return "backend-only"  # 检测失败时保守降级


def get_recommended_runners(project_type: str) -> list[str]:
    """根据项目类型获取推荐 runner 列表"""
    try:
        from detectors.project_type import get_recommended_runners as _get
        return _get(project_type)
    except ImportError:
        return ["openapi"]


def load_runner(name: str):
    """动态加载 runner 模块"""
    module_name = RUNNER_MODULES.get(name)
    if not module_name:
        return None
    if str(RUNNERS_DIR) not in sys.path:
        sys.path.insert(0, str(RUNNERS_DIR))
    try:
        return importlib.import_module(module_name)
    except ImportError as e:
        print(f"ERROR: 加载 runner '{name}' 失败: {e}", file=sys.stderr)
        return None


def merge_verdicts(verdicts: list[dict]) -> dict:
    """合并多个 runner 的 verdict"""
    overall = "PASS"
    total_passed = sum(v.get("passed", 0) for v in verdicts)
    total_failed = sum(v.get("failed", 0) for v in verdicts)
    total_tests  = sum(v.get("test_count", 0) for v in verdicts)
    all_failures = []
    for v in verdicts:
        failures = v.get("failures", [])
        if isinstance(failures, list):
            for f in failures:
                if isinstance(f, dict):
                    f["runner"] = v.get("runner", "unknown")
                    all_failures.append(f)

    for v in verdicts:
        if v.get("verdict") in ("FAIL", "ERROR"):
            overall = "FAIL"
            break

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "contract-test",
        "strategy": "multi-runner" if len(verdicts) > 1 else "single-runner",
        "verdict": overall,
        "project_type": verdicts[0].get("project_type", "unknown") if verdicts else "unknown",
        "runners": [v.get("runner", "?") for v in verdicts],
        "test_count": total_tests,
        "passed": total_passed,
        "failed": total_failed,
        "failures": all_failures[:20],
        "contract_violations": [],
        "next_action": "交付" if overall == "PASS" else "修复后重跑",
        "details": verdicts,
    }


def run_single_runner(runner_name: str, openapi: Path, base_url: str, output: str) -> dict:
    """运行单个 runner，返回其 verdict dict"""
    module = load_runner(runner_name)
    if not module:
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": "contract-test",
            "runner": runner_name,
            "verdict": "ERROR",
            "test_count": 0, "passed": 0, "failed": 0,
            "failures": [{"error": f"runner '{runner_name}' 未找到", "fix": "使用 --runner 指定可用 runner"}],
            "contract_violations": [],
            "next_action": "修复配置后重试",
        }
    exit_code = module.run(str(openapi), base_url, output)
    try:
        with open(output, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": "contract-test",
            "runner": runner_name,
            "verdict": "ERROR",
            "test_count": 0, "passed": 0, "failed": 0,
            "failures": [{"error": "verdict 文件未生成", "fix": "检查 runner 是否正常执行"}],
            "contract_violations": [],
            "next_action": "手动排查",
        }


def main() -> int:
    ap = argparse.ArgumentParser(description="contract-test 智能策略路由")
    ap.add_argument("--openapi", required=False, help="OpenAPI spec 路径")
    ap.add_argument("--base-url", required=False, default="http://localhost:8080", help="被测服务 base URL")
    ap.add_argument("--runner", default=None, help="指定 runner: openapi | playwright | all（默认自动推断）")
    ap.add_argument("--output", default=None, help="最终 verdict 输出路径")
    ap.add_argument("--detect-only", action="store_true", help="仅检测项目类型，不运行测试")
    ap.add_argument("--project-root", default=None, help="项目根目录（默认从 openapi 推断）")
    args = ap.parse_args()

    # 1. 检测项目类型（无需 openapi，--detect-only 也只需要这个）
    project_root = Path(args.project_root).resolve() if args.project_root else Path.cwd().resolve()
    project_type = detect_project_type(project_root)
    recommended = get_recommended_runners(project_type)

    print(f"[contract-test] project_type={project_type} project_root={project_root}")
    print(f"[contract-test] 推荐 runners: {', '.join(recommended)}")

    if args.detect_only:
        print(f"\n项目类型: {project_type}")
        print(f"推荐测试 runner: {', '.join(recommended)}")
        return 0

    # 2. openapi 文件（--detect-only 跳过）
    if not args.openapi:
        candidates = list(Path.cwd().rglob("openapi.yaml")) + list(Path.cwd().rglob("openapi.yml"))
        if candidates:
            args.openapi = str(candidates[0])
        else:
            print("ERROR: 未指定 --openapi，且未在当前目录找到 openapi.yaml/openapi.yml", file=sys.stderr)
            return 2

    openapi = Path(args.openapi).resolve()
    if not openapi.is_file():
        print(f"ERROR: OpenAPI 文件不存在: {openapi}", file=sys.stderr)
        return 2

    # 3. 确定要运行的 runner
    if args.runner and args.runner != "all":
        runners_to_run = [args.runner]
    elif args.runner == "all":
        runners_to_run = recommended
    else:
        runners_to_run = recommended

    # 验证 runner 可用性
    for rn in runners_to_run:
        if rn not in RUNNER_MODULES:
            print(f"ERROR: 未知 runner '{rn}'，可用: {', '.join(RUNNER_MODULES)}", file=sys.stderr)
            return 2

    # 设置输出目录
    verdicts_dir = REPORTS_DIR / "verdicts"
    output_dir = Path(os.environ.get("OUTPUT_DIR", verdicts_dir))
    output_dir.mkdir(parents=True, exist_ok=True)

    # 运行所有 runner
    verdicts: list[dict] = []
    runner_outputs: list[str] = []

    for runner_name in runners_to_run:
        ts_str = datetime.now().strftime("%Y%m%dT%H%M%S")
        runner_output = args.output or str(output_dir / f"{runner_name}_{ts_str}.json")
        runner_outputs.append(runner_output)

        print(f"\n{'='*60}")
        print(f"[contract-test] 运行 runner: {runner_name}")
        verdict = run_single_runner(runner_name, openapi, args.base_url, runner_output)
        verdict["project_type"] = project_type
        verdicts.append(verdict)

        print(f"[contract-test] {runner_name} verdict: {verdict.get('verdict')} "
              f"passed={verdict.get('passed')} failed={verdict.get('failed')}")

    # 汇总
    merged = merge_verdicts(verdicts)
    final_output = args.output or str(output_dir / f"summary_{datetime.now().strftime('%Y%m%dT%H%M%S')}.json")
    Path(final_output).parent.mkdir(parents=True, exist_ok=True)
    Path(final_output).write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"[contract-test] 汇总 verdict: {merged['verdict']}")
    print(f"[contract-test] 项目类型: {merged['project_type']}")
    print(f"[contract-test] 运行 runners: {', '.join(merged['runners'])}")
    print(f"[contract-test] 总测试: {merged['test_count']} passed={merged['passed']} failed={merged['failed']}")
    print(f"[contract-test] 详细报告: {final_output}")

    # 打印失败摘要
    if merged["failures"]:
        print(f"\n失败摘要 (共 {len(merged['failures'])} 条):")
        for f in merged["failures"][:5]:
            runner_tag = f"[{f.get('runner', '?')}]"
            test_name = f.get("test", "?")
            error = f.get("error", f.get("fix", ""))
            print(f"  {runner_tag} {test_name}: {error[:80]}")

    # 整体退出码
    return 0 if merged["verdict"] == "PASS" else 1


def _find_project_root(openapi_path: Path) -> Path:
    markers = ["pom.xml", "requirements.txt", "pyproject.toml", "setup.py",
              "go.mod", "Cargo.toml", "package.json"]
    cur = openapi_path.resolve().parent
    while cur != cur.parent:
        if any((cur / m).is_file() for m in markers):
            return cur
        cur = cur.parent
    return openapi_path.resolve().parent


if __name__ == "__main__":
    sys.exit(main())

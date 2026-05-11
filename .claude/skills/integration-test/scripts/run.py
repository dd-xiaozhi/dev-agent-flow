"""integration-test skill 主入口。

流程:
    1. 解析 CLI 参数（story_id / case_id / contract / project_root / handoff?）
    2. 探测 stack（stack_detect.py）
    3. 决定 ServiceConfig（handoff > stack 默认）
    4. service_runner 拉起服务，等健康检查
    5. 选 adapter，跑测试
    6. verdict_writer 写 JSON 到 INTEGRATION_TEST_REPORTS/<story>/<case>.json

退出码:
    0 = PASS
    1 = FAIL
    2 = ERROR（环境/配置问题，不是被测代码的锅）
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_THIS_DIR.parents[2] / "scripts"))

from adapters import AdapterResult, get_adapter  # noqa: E402
from paths import INTEGRATION_TEST_REPORTS, STATE_DIR  # noqa: E402
from service_runner import ServiceConfig, ServiceStartError, run_service  # noqa: E402
from stack_detect import ADAPTER_NOT_IMPLEMENTED, detect  # noqa: E402
from verdict_writer import write_verdict  # noqa: E402

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERROR = 2


def _check_uvx() -> bool:
    return shutil.which("uvx") is not None


def _emit_error_verdict(
    *,
    story_id: str,
    case_id: str,
    stack: str,
    adapter_name: str,
    error_message: str,
    log_path: Path,
    service_meta: dict | None = None,
    base_url: str | None = None,
) -> Path:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(error_message + "\n", encoding="utf-8")
    return write_verdict(
        story_id=story_id,
        case_id=case_id,
        stack=stack,
        adapter_name=adapter_name,
        result=AdapterResult(
            verdict="ERROR",
            error_message=error_message,
            raw_log_path=str(log_path),
        ),
        service_meta=service_meta,
        base_url=base_url,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="集成测试运行器（evaluator 调用）")
    parser.add_argument("--story-id", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--contract", type=Path, required=True, help="contract.md 路径")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="被测项目根目录（含 pom.xml/package.json/...）",
    )
    parser.add_argument(
        "--handoff",
        type=Path,
        help="generator handoff-artifact.md 路径（可选，读 service 段）",
    )
    parser.add_argument(
        "--health-timeout",
        type=int,
        default=30,
        help="服务健康检查超时秒数（默认 30）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只探测+打印计划，不启动服务")
    args = parser.parse_args(argv)

    log_dir = INTEGRATION_TEST_REPORTS / args.story_id
    log_path = log_dir / f"{args.case_id}.log"

    # 1. 探测 stack
    profile = detect(args.project_root)
    if profile.adapter == ADAPTER_NOT_IMPLEMENTED:
        msg = (
            f"stack={profile.stack} 暂不支持集成测试 adapter "
            f"(evidence={profile.evidence})"
        )
        print(json.dumps({"verdict": "ERROR", "reason": msg}, ensure_ascii=False))
        if not args.dry_run:
            _emit_error_verdict(
                story_id=args.story_id,
                case_id=args.case_id,
                stack=profile.stack,
                adapter_name=profile.adapter,
                error_message=msg,
                log_path=log_path,
            )
        return EXIT_ERROR

    # 2. ServiceConfig：handoff 优先，缺失走 stack 默认
    cfg = None
    if args.handoff:
        cfg = ServiceConfig.from_handoff(args.handoff)
    if cfg is None:
        cfg = ServiceConfig.default_for(profile.stack)
    if cfg is None:
        msg = f"无法确定服务启动配置（stack={profile.stack} 无默认值且 handoff 未提供 service 段）"
        print(json.dumps({"verdict": "ERROR", "reason": msg}, ensure_ascii=False))
        if not args.dry_run:
            _emit_error_verdict(
                story_id=args.story_id,
                case_id=args.case_id,
                stack=profile.stack,
                adapter_name=profile.adapter,
                error_message=msg,
                log_path=log_path,
            )
        return EXIT_ERROR

    parsed = urlparse(cfg.health_url)
    if parsed.scheme and parsed.netloc:
        base_url = f"{parsed.scheme}://{parsed.netloc}"
    else:
        base_url = f"http://localhost:{cfg.port}"

    plan = {
        "stack_profile": asdict(profile),
        "service_config": asdict(cfg),
        "adapter": profile.adapter,
        "base_url": base_url,
        "contract": str(args.contract),
        "verdict_output": str(INTEGRATION_TEST_REPORTS / args.story_id / f"{args.case_id}.json"),
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return EXIT_PASS

    # 3. 前置检查：uvx + contract 文件存在
    if not _check_uvx():
        msg = "uvx 未安装，schemathesis 无法运行。请先 `pip install uv`"
        _emit_error_verdict(
            story_id=args.story_id,
            case_id=args.case_id,
            stack=profile.stack,
            adapter_name=profile.adapter,
            error_message=msg,
            log_path=log_path,
        )
        print(msg, file=sys.stderr)
        return EXIT_ERROR

    if not args.contract.exists():
        msg = f"contract 文件不存在: {args.contract}"
        _emit_error_verdict(
            story_id=args.story_id,
            case_id=args.case_id,
            stack=profile.stack,
            adapter_name=profile.adapter,
            error_message=msg,
            log_path=log_path,
        )
        print(msg, file=sys.stderr)
        return EXIT_ERROR

    # 4. 拉起服务 + 5. 跑 adapter
    pid_path = STATE_DIR / "integration-test.pid"
    adapter = get_adapter(profile.adapter)
    service_meta = {**asdict(cfg), "started_at": None, "stopped_at": None, "pid": None}

    try:
        with run_service(
            cfg=cfg,
            project_root=args.project_root,
            log_path=log_dir / f"{args.case_id}.service.log",
            pid_path=pid_path,
            health_timeout_s=args.health_timeout,
        ) as handle:
            service_meta.update(
                started_at=handle.started_at,
                pid=handle.pid,
            )
            result = adapter.run(
                spec_path=args.contract,
                base_url=base_url,
                log_path=log_path,
                case_id=args.case_id,
            )
            service_meta["stopped_at"] = handle.stopped_at  # 在 with 退出后 service_runner 会更新
    except ServiceStartError as e:
        _emit_error_verdict(
            story_id=args.story_id,
            case_id=args.case_id,
            stack=profile.stack,
            adapter_name=profile.adapter,
            error_message=f"service start failed: {e}",
            log_path=log_path,
            service_meta=service_meta,
            base_url=base_url,
        )
        print(f"service start failed: {e}", file=sys.stderr)
        return EXIT_ERROR

    # 6. 写 verdict
    verdict_path = write_verdict(
        story_id=args.story_id,
        case_id=args.case_id,
        stack=profile.stack,
        adapter_name=profile.adapter,
        result=result,
        service_meta=service_meta,
        base_url=base_url,
    )
    print(f"verdict={result.verdict} written to {verdict_path}")

    if result.verdict == "PASS":
        return EXIT_PASS
    if result.verdict == "FAIL":
        return EXIT_FAIL
    return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())

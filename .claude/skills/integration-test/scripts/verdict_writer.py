"""把 AdapterResult 序列化为统一 verdict.json，写入 INTEGRATION_TEST_REPORTS。

产物按 role 分流：
    - <case>.generator.json —— generator 自验
    - <case>.evaluator.json —— evaluator 独立复跑（最终判定以此为准）

注意:
    - 本 writer 只负责"集成测试原始结果"持久化；
    - evaluator 最终 verdict 由 evaluator agent 自己写入 EVAL_VERDICTS
      （.chatlabs/reports/metrics/eval-verdicts.jsonl）。
    - 两者职责不重叠，schema 也不同。
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

# 让脚本能直接 `python verdict_writer.py` 时找到 paths
_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
from paths import INTEGRATION_TEST_REPORTS  # noqa: E402

from adapters import AdapterResult  # noqa: E402

SCHEMA_VERSION = "2.0"  # 2.0: 评分机制删除，verdict 二元化 + role 分流
VALID_ROLES = ("generator", "evaluator")


def write_verdict(
    *,
    story_id: str,
    case_id: str,
    stack: str,
    adapter_name: str,
    result: AdapterResult,
    service_meta: dict | None = None,
    base_url: str | None = None,
    role: str = "evaluator",
) -> Path:
    """写一份完整的 integration-test verdict 到
    INTEGRATION_TEST_REPORTS/<story>/<case>.<role>.json。

    Args:
        role: "generator" 或 "evaluator"，决定输出文件名后缀。
            evaluator 复跑结果是最终判定，generator 仅供自验比对。

    Returns:
        verdict 文件的绝对路径
    """
    if role not in VALID_ROLES:
        raise ValueError(f"role must be one of {VALID_ROLES}, got {role!r}")
    out_dir = INTEGRATION_TEST_REPORTS / story_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{case_id}.{role}.json"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "ts": datetime.now(timezone.utc).isoformat(),
        "story_id": story_id,
        "case_id": case_id,
        "role": role,
        "stack": stack,
        "adapter": adapter_name,
        "base_url": base_url,
        "verdict": result.verdict,
        "totals": result.totals,
        "failures": [asdict(f) for f in result.failures],
        "service": service_meta,
        "raw_log": result.raw_log_path,
        "error_message": result.error_message,
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path

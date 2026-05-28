#!/usr/bin/env python3
"""
ctx-guard — 强制 Context Reset hook

事件: UserPromptSubmit + PreToolUse
Matcher: ""（空，全匹配）

触发条件:
  - transcript_path 可用
  - context-probe 计算的 ctx_usage_pct > force_pct

行为:
  1. 读 config/thresholds.yaml 拿到 force_pct（默认 0.60）
  2. 调 scripts/context-probe.py 计算当前 ctx_usage_pct
  3. 超阈值 → exit 2 + stderr，Claude Code 视为 block

降级 / 阻断:
  - 阻断条件: ctx_usage_pct > force_pct → exit 2
  - 失败兜底: config / probe 缺失或 yaml 解析失败 → 降级默认值或静默退出，不阻断

产物:
  - .chatlabs/reports/hook-failures.log（异常时追加）
"""
import os
import sys
import json
import subprocess
from pathlib import Path

# 项目根（CLAUDE_PROJECT_DIR 优先,否则按 .claude/hooks/ 回退 2 级）
PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).resolve().parents[2])
))
REPORTS_DIR = PROJECT_DIR / ".chatlabs" / "reports"

CONFIG_PATH = PROJECT_DIR / "config" / "thresholds.yaml"
PROBE_PATH = PROJECT_DIR / "scripts" / "context-probe.py"
FAILURE_LOG = REPORTS_DIR / "hook-failures.log"
DEFAULT_FORCE_PCT = 0.60


def log_failure(msg: str):
    try:
        FAILURE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(FAILURE_LOG, "a") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def load_force_pct() -> float:
    """优先读 YAML，失败则降级到朴素行解析，再失败用默认值"""
    # 降级 1：config 目录不存在
    if not CONFIG_PATH.exists():
        return DEFAULT_FORCE_PCT
    try:
        import yaml  # type: ignore
        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}
        return float(cfg.get("context_reset", {}).get("force_pct", DEFAULT_FORCE_PCT))
    except Exception:
        pass
    # 降级 2：朴素解析
    try:
        text = CONFIG_PATH.read_text()
        in_ctx = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("context_reset:"):
                in_ctx = True
                continue
            if in_ctx and stripped.startswith("force_pct:"):
                return float(stripped.split(":", 1)[1].strip())
            if in_ctx and line and not line.startswith((" ", "\t")):
                break
    except Exception:
        pass
    return DEFAULT_FORCE_PCT


def main():
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    force_pct = load_force_pct()
    transcript_path = hook_input.get("transcript_path")
    model = hook_input.get("model", "opus-4-7")

    if not transcript_path:
        sys.exit(0)

    # 降级：context-probe.py 不存在 → 静默放行
    if not PROBE_PATH.exists():
        sys.exit(0)

    try:
        probe_input = json.dumps({"transcript_path": transcript_path, "model": model})
        result = subprocess.run(
            ["python", str(PROBE_PATH)],
            input=probe_input,
            capture_output=True,
            text=True,
            timeout=5,
        )
        probe = json.loads(result.stdout or "{}")
    except Exception:
        # 降级：probe 失败 → 静默放行
        sys.exit(0)

    pct = probe.get("ctx_usage_pct", 0.0)
    tokens = probe.get("tokens", 0)

    if pct > force_pct:
        msg = (
            f"[ctx-guard] Context 占用 {pct:.1%} ({tokens} tokens) "
            f"超过硬阈值 {force_pct:.0%}。\n"
            f"→ 请调用 /context-reset skill 产出 handoff 工件，在新 session 继续。\n"
            f"→ 依据：.claude/skills/context-reset/SKILL.md\n"
            f"→ 调整阈值：config/thresholds.yaml::context_reset.force_pct（如目录存在）"
        )
        print(msg, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()

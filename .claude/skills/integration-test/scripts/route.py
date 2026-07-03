"""integration-test/route.py — 薄路由,给主 Claude 提建议该调哪个 testing skill。

职责:
  - 读 <project_root>/docs/env.yaml.testing.skill (优先级 1,显式)
  - 缺失 → 按文件名约定 fallback (优先级 2)
  - 找不到 → 报 ERROR,调用方据此让 verdict=ERROR

输出 JSON 给主 Claude 消费(不直接调 skill,skill 调用是 Skill 工具职责):
  {"ok": true, "skill": "java-testing", "source": "env.yaml" | "convention" | "force"}
  {"ok": false, "error": "...", "candidates": [...]}

依赖: Python 标准库
"""
from __future__ import annotations

import argparse
import json
import yaml
import sys
from pathlib import Path

# 文件名约定 fallback —— 新增语言时在此加一行,无需动 evaluator / integration-test/SKILL.md
CONVENTION: dict[str, str] = {
    "pom.xml": "java-testing",
    "package.json": "frontend-testing",
    "requirements.txt": "python-testing",
    "pyproject.toml": "python-testing",
    "go.mod": "go-testing",
    "Cargo.toml": "rust-testing",
}


def route(project_root: Path, force_stack: str | None = None) -> dict:
    """返回应当委托给哪个 testing skill。"""
    # 优先级 0: --force-stack 显式指定
    if force_stack:
        return {"ok": True, "skill": f"{force_stack}-testing", "source": "force"}

    # 优先级 1: env.yaml.testing.skill
    cfg_path = project_root / "docs" / "env.yaml"
    if cfg_path.exists():
        try:
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
            skill = (cfg.get("testing") or {}).get("skill")
            if skill:
                return {"ok": True, "skill": skill, "source": "env.yaml"}
        except json.JSONDecodeError:
            pass  # 配置坏了不阻断,走 fallback

    # 优先级 2: 文件名约定 fallback (按 CONVENTION 顺序探测)
    for filename, skill in CONVENTION.items():
        if (project_root / filename).exists():
            return {"ok": True, "skill": skill, "source": "convention",
                    "matched_file": filename}

    # 都没命中
    return {
        "ok": False,
        "error": "no testing skill resolved",
        "hint": "在项目 docs/env.yaml 加 testing.skill 字段,或在项目根放入 pom.xml/package.json/requirements.txt 等",
        "candidates": sorted(set(CONVENTION.values())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="integration-test 路由器")
    parser.add_argument("--project-root", default=".", help="项目根目录,默认 cwd")
    parser.add_argument("--force-stack", default=None,
                        help="强制指定栈(java/frontend/python/go/rust),跳过探测")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    result = route(project_root, force_stack=args.force_stack)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())

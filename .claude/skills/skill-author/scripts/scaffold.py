"""scaffold.py — Skill 骨架生成器

按 Anthropic 6 铁律 + 本项目约定，一键生成 skill 目录骨架。

CLI:
  python scaffold.py create <name> --type <type> --description <desc> [options]
      创建新 skill 目录 + SKILL.md 骨架 + 可选 scripts/ + references/
      stdout: {"ok": true, "path": "...", "files_created": [...]}

  python scaffold.py check <name>
      检查现有 skill 是否符合最佳实践（自检清单 7 项）
      stdout: {"ok": bool, "checks": {...}, "issues": [...]}

  python scaffold.py list
      列出所有 9 类 skill 现状（已有 / 盲区）
      stdout: {"types": {...}}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# 项目根（CLAUDE_PROJECT_DIR 优先,否则按 .claude/skills/<x>/scripts/ 回退 4 级）
PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).absolute().parents[4])
))
CLAUDE_DIR = PROJECT_DIR / ".claude"


SKILLS_DIR = CLAUDE_DIR / "skills"

SKILL_TYPES = {
    "knowledge": "知识/参考 — 教 Claude 用某 lib/工具,避坑",
    "validation": "验证 — 自动化检查代码/契约是否符合规则",
    "data-access": "数据访问 — 从外部系统拿数据(日志/API/DB)",
    "automation": "自动化 — 把多步操作压成单命令",
    "scaffold": "脚手架 — 生成新文件/项目骨架",
    "code-review": "代码审查 — 检查既有代码质量",
    "deployment": "部署 — 触发构建/发布",
    "debug": "调试 — 给现象/告警 → 输出排查报告",
    "operation": "运维 — 清理/回收/迁移共享资源(dry-run 优先)",
}


# ── SKILL.md 模板 ─────────────────────────────────────────────

SKILL_MD_TEMPLATE = """---
name: {name}
description: "{description}"
model: {model}
{rules_block}---

# {title}

> _TBD: 一句话定位（slogan-level，由作者补全）_

## 触发

_TBD: 列触发关键词,逗号分隔,最短化_

## 边界

- ✅ _TBD: 做什么 1_
- ✅ _TBD: 做什么 2_
- ❌ _TBD: 不做什么 1_
- ❌ _TBD: 不做什么 2_

## Gotchas

_⚠️ 上线时先留空。等真实使用 3-5 次踩到坑后回填。_
_不要凭空猜测"AI 可能会..." 级别的内容。_

{cli_block}
## 流程

```mermaid
flowchart LR
  A[step 1] --> B[step 2]
  B --> C[step 3]
```

## 关联

{related_block}"""


# ── helper.py 模板 ────────────────────────────────────────────

HELPER_PY_TEMPLATE = '''"""helper.py — {name} helper 脚本

CLI:
  python helper.py <sub> [args]    # TBD: 子命令说明
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# 项目根（CLAUDE_PROJECT_DIR 优先,否则按 .claude/skills/<x>/scripts/ 回退 4 级）
PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).absolute().parents[4])
))
PROJECT_CONFIG = PROJECT_DIR / ".chatlabs" / "project-config.json"

# 如需访问 task.json,取消下两行注释:
# sys.path.insert(0, str(PROJECT_DIR / ".claude" / "skills" / "task" / "scripts"))
# from task_store import TaskJsonStore


def cmd_example(args) -> int:
    """示例子命令"""
    result = {{"ok": True, "echo": args.text}}
    print(json.dumps(result, ensure_ascii=False))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="{name} helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_e = sub.add_parser("example", help="example subcommand")
    p_e.add_argument("text")
    p_e.set_defaults(func=cmd_example)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
'''


# ── 子命令实现 ───────────────────────────────────────────────

def cmd_create(args) -> int:
    if args.type not in SKILL_TYPES:
        print(json.dumps({
            "ok": False,
            "error": f"unknown type '{args.type}'",
            "valid_types": list(SKILL_TYPES.keys()),
        }, ensure_ascii=False, indent=2))
        return 1

    skill_dir = SKILLS_DIR / args.name
    if skill_dir.exists():
        print(json.dumps({
            "ok": False,
            "error": f"skill '{args.name}' already exists at {skill_dir.relative_to(PROJECT_DIR)}",
        }, ensure_ascii=False, indent=2))
        return 1

    files_created: list[str] = []
    skill_dir.mkdir(parents=True)

    # ── 生成 SKILL.md ─────────────────────────────────────
    rules_block = ""
    if args.rules:
        rules_lines = "\n".join(f"  - {r}" for r in args.rules)
        rules_block = f"rules:\n{rules_lines}\n"

    cli_block = ""
    if args.with_scripts:
        cli_block = f"""## CLI

```bash
python .claude/skills/{args.name}/scripts/helper.py <sub> [args]
```

"""

    related_lines = []
    if args.with_scripts:
        related_lines.append(f"- 脚本：`.claude/skills/{args.name}/scripts/helper.py`")
    if args.with_references:
        related_lines.append(f"- 详细参考：`.claude/skills/{args.name}/references/`")
    related_lines.append("- _TBD: 配置文件 / 调用方 / 关联 skill_")
    related_block = "\n".join(related_lines)

    title = args.name.replace("-", " ").title()
    skill_md = SKILL_MD_TEMPLATE.format(
        name=args.name,
        description=args.description,
        model=args.model,
        rules_block=rules_block,
        title=title,
        cli_block=cli_block,
        related_block=related_block,
    )
    skill_md_path = skill_dir / "SKILL.md"
    skill_md_path.write_text(skill_md, encoding="utf-8")
    files_created.append(str(skill_md_path.relative_to(PROJECT_DIR)))

    # ── 生成 scripts/ ───────────────────────────────────
    if args.with_scripts:
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "__init__.py").write_text("", encoding="utf-8")
        files_created.append(str((scripts_dir / "__init__.py").relative_to(PROJECT_DIR)))

        helper_path = scripts_dir / "helper.py"
        helper_path.write_text(HELPER_PY_TEMPLATE.format(name=args.name), encoding="utf-8")
        files_created.append(str(helper_path.relative_to(PROJECT_DIR)))

    # ── 生成 references/ ────────────────────────────────
    if args.with_references:
        refs_dir = skill_dir / "references"
        refs_dir.mkdir()
        (refs_dir / ".gitkeep").write_text("", encoding="utf-8")
        files_created.append(str((refs_dir / ".gitkeep").relative_to(PROJECT_DIR)))

    print(json.dumps({
        "ok": True,
        "path": str(skill_dir.relative_to(PROJECT_DIR)),
        "type": args.type,
        "type_desc": SKILL_TYPES[args.type],
        "files_created": files_created,
        "next_steps": [
            "1. 编辑 SKILL.md：填触发段 / 边界段（✅❌）",
            "2. 跑通最简 CLI（如有 scripts）",
            "3. 真实场景试用 3-5 次,踩坑后回填 Gotchas",
            "4. 完成自检：python scaffold.py check " + args.name,
        ],
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_check(args) -> int:
    skill_dir = SKILLS_DIR / args.name
    if not skill_dir.exists():
        print(json.dumps({"ok": False, "error": f"skill not found: {args.name}"}, ensure_ascii=False))
        return 1

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        print(json.dumps({"ok": False, "error": "SKILL.md missing"}, ensure_ascii=False))
        return 1

    content = skill_md.read_text(encoding="utf-8")
    lines = content.splitlines()
    line_count = len(lines)

    checks: dict[str, bool] = {}
    issues: list[str] = []

    # 1. frontmatter 4 字段
    fm_text = content.split("---", 2)[1] if content.startswith("---") else ""
    checks["frontmatter_name"] = f"name: {args.name}" in fm_text
    checks["frontmatter_description"] = "description:" in fm_text
    checks["frontmatter_model"] = "model:" in fm_text
    if not checks["frontmatter_name"]:
        issues.append("frontmatter name 字段缺失或与目录名不匹配")
    if not checks["frontmatter_description"]:
        issues.append("frontmatter description 字段缺失")
    if not checks["frontmatter_model"]:
        issues.append("frontmatter model 字段缺失")

    # 2. description TRIGGER 风格
    checks["description_trigger_style"] = "USE WHEN" in fm_text or "TRIGGER" in fm_text
    if not checks["description_trigger_style"]:
        issues.append("description 不是 TRIGGER 风格(应含 USE WHEN 或 TRIGGER)")

    # 3. Gotchas 段
    checks["gotchas_section"] = "## Gotchas" in content
    if not checks["gotchas_section"]:
        issues.append("缺少 ## Gotchas 段")

    # 4. 边界段
    checks["boundary_section"] = ("## 边界" in content) and ("✅" in content) and ("❌" in content)
    if not checks["boundary_section"]:
        issues.append("缺少完整边界段(需含 ✅ 和 ❌)")

    # 5. 主文件长度
    checks["main_file_under_200"] = line_count <= 200
    if not checks["main_file_under_200"]:
        issues.append(f"主文件 {line_count} 行,超过 200 行,考虑拆 references")

    # 6. scripts 目录（如有）
    scripts_dir = skill_dir / "scripts"
    checks["has_scripts"] = scripts_dir.exists()
    if scripts_dir.exists():
        py_files = list(scripts_dir.glob("*.py"))
        checks["scripts_has_py"] = len([f for f in py_files if f.name != "__init__.py"]) > 0
        if not checks["scripts_has_py"]:
            issues.append("scripts/ 目录存在但无 .py 业务脚本")

    # 7. Gotchas 段非空（不含 TBD 占位）
    if checks["gotchas_section"]:
        gotchas_idx = content.find("## Gotchas")
        next_section = content.find("\n## ", gotchas_idx + 1)
        gotchas_body = content[gotchas_idx:next_section if next_section > 0 else len(content)]
        checks["gotchas_non_empty"] = "TBD" not in gotchas_body and "留空" not in gotchas_body
        if not checks["gotchas_non_empty"]:
            issues.append("Gotchas 段仍是占位状态,实际使用后请回填")

    all_pass = all(checks.values())
    print(json.dumps({
        "ok": all_pass,
        "skill": args.name,
        "line_count": line_count,
        "checks": checks,
        "issues": issues,
        "verdict": "PASS" if all_pass else "FAIL",
    }, ensure_ascii=False, indent=2))
    return 0 if all_pass else 1


def cmd_list(args) -> int:
    existing: dict[str, list[str]] = {t: [] for t in SKILL_TYPES}
    existing["unknown"] = []

    if not SKILLS_DIR.exists():
        print(json.dumps({"ok": False, "error": f"skills dir not found: {SKILLS_DIR}"}, ensure_ascii=False))
        return 1

    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir():
            continue
        skill_md = d / "SKILL.md"
        if not skill_md.exists():
            continue
        # 简单从 description 中推断 type（启发式）
        # 这里不强制要求 frontmatter 声明 type,只列出
        existing["unknown"].append(d.name)

    # 因为暂未在 frontmatter 引入 type 字段,所有 skill 归入 unknown
    # 用户可手动按类映射
    result = {
        "ok": True,
        "skill_types": {k: {"desc": v, "count_in_project": "(手动映射)"} for k, v in SKILL_TYPES.items()},
        "all_skills": existing["unknown"],
        "total": len(existing["unknown"]),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Skill scaffold helper (按 Anthropic 6 铁律 + 项目约定)")
    sub = p.add_subparsers(dest="cmd", required=True)

    # create
    p_c = sub.add_parser("create", help="create new skill from template")
    p_c.add_argument("name", help="skill name (kebab-case)")
    p_c.add_argument("--type", required=True, choices=list(SKILL_TYPES.keys()),
                     help="skill type (one of 9 categories)")
    p_c.add_argument("--description", required=True,
                     help="TRIGGER style: USE WHEN ... OUTPUT ... DO NOT USE ...")
    p_c.add_argument("--with-scripts", action="store_true", default=True,
                     help="create scripts/ directory with helper.py (default true)")
    p_c.add_argument("--no-scripts", dest="with_scripts", action="store_false",
                     help="skip scripts/ directory")
    p_c.add_argument("--with-references", action="store_true", default=False,
                     help="create references/ directory")
    p_c.add_argument("--model", choices=("haiku", "sonnet", "opus"), default="sonnet")
    p_c.add_argument("--rules", nargs="*", default=[],
                     help="rules to reference (e.g. agent-conventions)")
    p_c.set_defaults(func=cmd_create)

    # check
    p_k = sub.add_parser("check", help="check existing skill against best practices")
    p_k.add_argument("name", help="skill name")
    p_k.set_defaults(func=cmd_check)

    # list
    p_l = sub.add_parser("list", help="list all skills with 9-type categorization")
    p_l.set_defaults(func=cmd_list)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

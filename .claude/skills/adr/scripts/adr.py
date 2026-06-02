#!/usr/bin/env python3
"""ADR 管理辅助脚本(零第三方依赖)。

用法:
  python3 adr.py new "决策标题" --dir docs/adr [--slug my-slug]
                                [--supersedes N] [--status Accepted]
  python3 adr.py index --dir docs/adr

设计原则:
  - 编号四位、连续递增、永不复用。
  - 文件名用英文 slug(即便正文是中文),便于跨工具处理。
  - 取代旧决策时,新建一条并把旧的状态标记为 Superseded(不删除、不改正文)。
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

FILENAME_RE = re.compile(r"^(\d{4})-(.+)\.md$")
TITLE_RE = re.compile(r"^#\s+ADR-\d+\s*:?\s*(.*)$")


def find_adrs(adr_dir: Path):
    """返回 [(num:int, path:Path)],按编号升序。"""
    items = []
    for p in sorted(adr_dir.glob("*.md")):
        if p.name.lower() == "readme.md":
            continue
        m = FILENAME_RE.match(p.name)
        if m:
            items.append((int(m.group(1)), p))
    items.sort(key=lambda x: x[0])
    return items


def next_number(adr_dir: Path) -> int:
    items = find_adrs(adr_dir)
    return (items[-1][0] + 1) if items else 1


def slugify(text: str) -> str:
    """从标题生成英文 slug。若标题不含可用 ASCII 字符,返回空串。"""
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


def parse_status(path: Path) -> str:
    """读取一条 ADR 的状态(Status 段里第一行非空、非注释的内容)。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    in_status = False
    in_comment = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_status:  # 已离开 Status 段
                break
            in_status = stripped.lower() == "## status"
            continue
        if not in_status:
            continue
        if "<!--" in stripped:
            in_comment = True
        if in_comment:
            if "-->" in stripped:
                in_comment = False
            continue
        if stripped:
            return stripped
    return "Unknown"


def parse_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        m = TITLE_RE.match(line.strip())
        if m:
            return m.group(1).strip() or path.stem
        if line.strip().startswith("# "):
            return line.strip()[2:].strip()
    return path.stem


def set_status(path: Path, new_status: str) -> None:
    """只改 Status 段第一行内容,正文其余部分保持不变。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    out, in_status, in_comment, done = [], False, False, False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            in_status = stripped.lower() == "## status"
            out.append(line)
            continue
        if in_status and not done:
            if "<!--" in stripped:
                in_comment = True
            if in_comment:
                out.append(line)
                if "-->" in stripped:
                    in_comment = False
                continue
            if stripped:  # 第一行实际状态值,替换它
                out.append(new_status)
                done = True
                continue
        out.append(line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def cmd_new(args):
    adr_dir = Path(args.dir)
    adr_dir.mkdir(parents=True, exist_ok=True)

    slug = args.slug or slugify(args.title)
    if not slug:
        sys.exit("标题不含可用的英文字符,请用 --slug 指定英文文件名,例如 --slug use-event-sourcing")

    num = next_number(adr_dir)
    num_str = f"{num:04d}"
    path = adr_dir / f"{num_str}-{slug}.md"
    if path.exists():
        sys.exit(f"文件已存在:{path}")

    today = datetime.date.today().isoformat()
    status = args.status or "Proposed"

    supersedes_line = ""
    if args.supersedes:
        old = dict((n, p) for n, p in find_adrs(adr_dir)).get(args.supersedes)
        if not old:
            sys.exit(f"找不到要取代的 ADR-{args.supersedes:04d}")
        supersedes_line = f"\nSupersedes ADR-{args.supersedes:04d}\n"
        set_status(old, f"Superseded by ADR-{num_str}")
        print(f"已将 {old.name} 状态标记为 Superseded by ADR-{num_str}")

    body = (
        f"# ADR-{num_str}: {args.title}\n\n"
        f"## Status\n\n{status}\n{supersedes_line}\n"
        f"## Context\n\n"
        f"<!-- 同时写业务背景与技术背景,只摆事实不下结论。决策日期:{today} -->\n\n"
        f"## Decision\n\n"
        f"<!-- 用主动语气:\"我们将采用……\" -->\n\n"
        f"## Consequences\n\n"
        f"<!-- 正面和负面都要写 -->\n"
    )
    path.write_text(body, encoding="utf-8")
    print(f"已创建:{path}")
    print("下一步:填充 Context / Decision / Consequences,然后运行 `index` 重新生成索引。")


def cmd_index(args):
    adr_dir = Path(args.dir)
    if not adr_dir.exists():
        sys.exit(f"目录不存在:{adr_dir}")
    items = find_adrs(adr_dir)

    rows = []
    for num, path in items:
        title = parse_title(path)
        status = parse_status(path)
        rows.append(f"| [ADR-{num:04d}]({path.name}) | {title} | {status} |")

    table = "\n".join(rows) if rows else "| _(暂无)_ | | |"
    content = (
        "# 架构决策记录(ADR)\n\n"
        "本目录记录项目的架构决策。每条 ADR 都是不可变的:决策变更时新增一条,"
        "并将被取代的旧记录标记为 Superseded,以保留决策的演化历史。\n\n"
        "| 编号 | 标题 | 状态 |\n"
        "| --- | --- | --- |\n"
        f"{table}\n"
    )
    (adr_dir / "README.md").write_text(content, encoding="utf-8")
    print(f"已生成索引:{adr_dir / 'README.md'}({len(items)} 条 ADR)")


def main():
    parser = argparse.ArgumentParser(description="ADR 管理辅助脚本")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="新建一条 ADR")
    p_new.add_argument("title", help="决策标题(可中文)")
    p_new.add_argument("--dir", default="docs/adr", help="ADR 目录,默认 docs/adr")
    p_new.add_argument("--slug", help="英文文件名 slug(标题非英文时必填)")
    p_new.add_argument("--supersedes", type=int, help="本决策取代的旧 ADR 编号")
    p_new.add_argument("--status", help="初始状态,默认 Proposed")
    p_new.set_defaults(func=cmd_new)

    p_idx = sub.add_parser("index", help="生成/更新 README 索引")
    p_idx.add_argument("--dir", default="docs/adr", help="ADR 目录,默认 docs/adr")
    p_idx.set_defaults(func=cmd_index)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

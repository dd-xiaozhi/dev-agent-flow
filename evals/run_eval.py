"""
run_eval.py — golden task 要点清单核对 harness

问题：改 agent prompt / flow 模板后无回归手段，全靠感觉。前沿经验——prompt
迭代是多代理系统的主要改进杠杆，没有 eval 就是盲改。

本 harness 用**要点清单核对**（而非全文 diff）守护回归：LLM 产出非确定，全文
diff 无意义；但"该出现的字段/端点/决策是否出现、该禁止的越界是否出现"是确定的。

工作方式：
1. golden task 在 `golden/<id>/manifest.json` 声明 must_contain / must_not_contain 断言
2. 跑完 flow 产出真实 artifact 后，`run <id> --produced <task_dir>` 核对断言
3. `selftest <id>` 用 golden 自带的 expected/ 作 produced，证明 harness + manifest 自洽
   （framework 仓无 live agent，selftest 是常驻可跑的回归底线）

manifest.json schema:
{
  "id": "g1-...",
  "description": "...",
  "flow_id": "local-spec",            # 该 golden 走哪个 flow（信息用途）
  "target_artifact": "contract.md",   # 默认核对的产物文件名
  "assertions": {
    "must_contain":     [{"name": "...", "pattern": "<regex>", "artifact": "<可选,覆盖 target>"}],
    "must_not_contain": [{"name": "...", "pattern": "<regex>", "artifact": "<可选>"}]
  }
}

Usage:
    python evals/run_eval.py list
    python evals/run_eval.py selftest g1-contract-quality
    python evals/run_eval.py selftest --all
    python evals/run_eval.py run g1-contract-quality --produced docs/task/store/<story_id>

退出码：0 = 全 PASS / 1 = 有 FAIL 或错误。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
GOLDEN_DIR = EVALS_DIR / "golden"


def _load_manifest(golden_id: str) -> dict:
    path = GOLDEN_DIR / golden_id / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_artifact(produced_dir: Path, artifact_name: str) -> str | None:
    p = produced_dir / artifact_name
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def _check(manifest: dict, produced_dir: Path) -> dict:
    """对 produced_dir 里的 artifact 逐条断言核对。"""
    target = manifest.get("target_artifact", "contract.md")
    assertions = manifest.get("assertions", {})
    results: list[dict] = []

    def _run_group(group: list[dict], kind: str) -> None:
        for a in group:
            artifact = a.get("artifact", target)
            content = _read_artifact(produced_dir, artifact)
            name = a.get("name", a.get("pattern", "?"))
            if content is None:
                results.append({"name": name, "kind": kind, "artifact": artifact,
                                "status": "FAIL", "reason": f"artifact 缺失: {artifact}"})
                continue
            found = re.search(a["pattern"], content) is not None
            if kind == "must_contain":
                ok = found
                reason = None if ok else f"缺少匹配 /{a['pattern']}/"
            else:  # must_not_contain
                ok = not found
                reason = None if ok else f"出现禁止内容 /{a['pattern']}/（越界）"
            results.append({"name": name, "kind": kind, "artifact": artifact,
                            "status": "PASS" if ok else "FAIL", "reason": reason})

    _run_group(assertions.get("must_contain", []), "must_contain")
    _run_group(assertions.get("must_not_contain", []), "must_not_contain")

    failed = [r for r in results if r["status"] == "FAIL"]
    return {
        "id": manifest.get("id"),
        "produced_dir": str(produced_dir),
        "verdict": "PASS" if not failed else "FAIL",
        "total": len(results),
        "failed": len(failed),
        "results": results,
    }


def cmd_list(_args: argparse.Namespace) -> int:
    if not GOLDEN_DIR.exists():
        print(json.dumps({"ok": True, "golden": []}, ensure_ascii=False))
        return 0
    items = []
    for d in sorted(GOLDEN_DIR.iterdir()):
        if (d / "manifest.json").exists():
            m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
            items.append({"id": m.get("id", d.name), "flow_id": m.get("flow_id"),
                          "description": m.get("description")})
    print(json.dumps({"ok": True, "golden": items}, ensure_ascii=False, indent=2))
    return 0


def _report(res: dict) -> None:
    print(json.dumps({"ok": res["verdict"] == "PASS", **res}, ensure_ascii=False, indent=2))


def cmd_selftest(args: argparse.Namespace) -> int:
    ids = ([d.name for d in sorted(GOLDEN_DIR.iterdir()) if (d / "manifest.json").exists()]
           if args.all else [args.golden_id])
    all_pass = True
    for gid in ids:
        manifest = _load_manifest(gid)
        expected_dir = GOLDEN_DIR / gid / "expected"
        res = _check(manifest, expected_dir)
        _report(res)
        all_pass = all_pass and res["verdict"] == "PASS"
    return 0 if all_pass else 1


def cmd_run(args: argparse.Namespace) -> int:
    manifest = _load_manifest(args.golden_id)
    res = _check(manifest, Path(args.produced))
    _report(res)
    return 0 if res["verdict"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="golden task 要点清单核对 harness")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="列出所有 golden task").set_defaults(func=cmd_list)

    p_st = sub.add_parser("selftest", help="用 golden 的 expected/ 作 produced 自检")
    p_st.add_argument("golden_id", nargs="?", default=None)
    p_st.add_argument("--all", action="store_true", help="自检所有 golden task")
    p_st.set_defaults(func=cmd_selftest)

    p_run = sub.add_parser("run", help="核对真实产出目录")
    p_run.add_argument("golden_id")
    p_run.add_argument("--produced", required=True, help="跑完 flow 的 task 产物目录")
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    if getattr(args, "cmd", None) == "selftest" and not args.all and not args.golden_id:
        parser.error("selftest 需要 <golden_id> 或 --all")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

"""技术栈探测：根据项目根目录的清单文件特征识别 stack。

Public API:
    detect(project_root: Path) -> StackProfile

退出码（CLI 模式）:
    0 = 成功探测（含 unknown / unsupported，由调用方决定后续行为）

边界:
    - 仅做文件存在性 + 关键依赖关键字检查，不解析完整 AST
    - 多命中按优先级（spring-boot > fastapi > node-http > web-frontend > unknown）
    - web-frontend 暂不支持，但能识别（用于明确报错而不是误判 unknown）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ADAPTER_HTTP_SCHEMATHESIS = "http-schemathesis"
ADAPTER_NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


@dataclass
class StackProfile:
    """技术栈探测结果。"""

    stack: str  # spring-boot / fastapi / node-http / web-frontend / unknown
    adapter: str  # 对应 adapter 名；NOT_IMPLEMENTED 表示已识别但本期不支持
    project_root: str
    evidence: list[str]  # 命中证据（文件路径 + 关键字），便于排查误判


def _read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _detect_spring_boot(root: Path) -> tuple[bool, list[str]]:
    pom = root / "pom.xml"
    gradle_kts = root / "build.gradle.kts"
    gradle = root / "build.gradle"
    for f in (pom, gradle_kts, gradle):
        if not f.exists():
            continue
        content = _read_text_safe(f)
        if "spring-boot-starter" in content or "org.springframework.boot" in content:
            return True, [f"{f.name}:spring-boot-starter"]
    return False, []


def _detect_fastapi(root: Path) -> tuple[bool, list[str]]:
    candidates = [root / "pyproject.toml", root / "requirements.txt", root / "Pipfile"]
    for f in candidates:
        if not f.exists():
            continue
        content = _read_text_safe(f).lower()
        if re.search(r"\bfastapi\b", content):
            return True, [f"{f.name}:fastapi"]
    return False, []


def _detect_node_http(root: Path) -> tuple[bool, list[str]]:
    pkg = root / "package.json"
    if not pkg.exists():
        return False, []
    try:
        data = json.loads(_read_text_safe(pkg) or "{}")
    except json.JSONDecodeError:
        return False, []
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    backend_keys = {"express", "koa", "@nestjs/core", "fastify", "hapi"}
    hits = backend_keys & set(deps.keys())
    if hits:
        return True, [f"package.json:{','.join(sorted(hits))}"]
    return False, []


def _detect_web_frontend(root: Path) -> tuple[bool, list[str]]:
    pkg = root / "package.json"
    if not pkg.exists():
        return False, []
    try:
        data = json.loads(_read_text_safe(pkg) or "{}")
    except json.JSONDecodeError:
        return False, []
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    frontend_keys = {"react", "vue", "next", "nuxt", "@angular/core", "svelte"}
    hits = frontend_keys & set(deps.keys())
    if hits:
        return True, [f"package.json:{','.join(sorted(hits))}"]
    return False, []


def detect(project_root: Path) -> StackProfile:
    """按优先级探测 stack。

    Args:
        project_root: 项目根目录（含 pom.xml/package.json/...）

    Returns:
        StackProfile：stack 字段必填，adapter 由 stack 决定
    """
    root = project_root.resolve()
    if not root.is_dir():
        return StackProfile(
            stack="unknown",
            adapter=ADAPTER_NOT_IMPLEMENTED,
            project_root=str(root),
            evidence=[f"project_root not a directory: {root}"],
        )

    # 优先级：后端框架优先（HTTP 闭环），前端最后（用于明确报错）
    for name, fn in (
        ("spring-boot", _detect_spring_boot),
        ("fastapi", _detect_fastapi),
        ("node-http", _detect_node_http),
    ):
        hit, evidence = fn(root)
        if hit:
            return StackProfile(
                stack=name,
                adapter=ADAPTER_HTTP_SCHEMATHESIS,
                project_root=str(root),
                evidence=evidence,
            )

    fe_hit, fe_evidence = _detect_web_frontend(root)
    if fe_hit:
        return StackProfile(
            stack="web-frontend",
            adapter=ADAPTER_NOT_IMPLEMENTED,
            project_root=str(root),
            evidence=fe_evidence,
        )

    return StackProfile(
        stack="unknown",
        adapter=ADAPTER_NOT_IMPLEMENTED,
        project_root=str(root),
        evidence=["no recognizable manifest"],
    )


def _main() -> int:
    parser = argparse.ArgumentParser(description="探测项目技术栈，输出 JSON profile")
    parser.add_argument("project_root", type=Path, help="项目根目录")
    args = parser.parse_args()

    profile = detect(args.project_root)
    print(json.dumps(asdict(profile), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main())

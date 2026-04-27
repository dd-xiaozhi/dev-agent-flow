#!/usr/bin/env python3
"""
项目类型检测器
检测当前项目是：纯后端 | 前后端分离 | SPA 前端独立 | 微服务
"""
from __future__ import annotations

import re
from pathlib import Path


def detect_project_type(project_root: Path | str | None = None) -> str:
    """
    检测项目类型，返回：
      - backend-only    : 纯后端（Java/Python/Go 等，无前端资产）
      - frontend-backend: 前后端混合（前端代码 + 后端 API）
      - spa             : SPA 独立前端（React/Vue/Angular，无后端同仓）
      - microservices   : 微服务（多个 api/ 或 proto/ 子目录）

    检测策略（按优先级）：
      1. 根目录 package.json + 无后端根目录 → spa
      2. 存在 frontend/ | client/ | web/ 等前端目录 → frontend-backend
      3. 存在 src/main/java 或 src/main/kotlin → backend-only (Java)
      4. requirements.txt / pyproject.toml / setup.py → backend-only (Python)
      5. 存在 api/ 子目录且包含多个服务 → microservices
      6. 默认 → backend-only
    """
    if project_root is None:
        project_root = Path.cwd()
    elif isinstance(project_root, str):
        project_root = Path(project_root)
    project_root = project_root.resolve()

    # 1. SPA 检测
    if (project_root / "package.json").is_file():
        pkg = _read_json_field(project_root / "package.json", "name")
        # 如果根目录是纯前端项目（非 workspace monorepo root）
        backend_markers = [
            "pom.xml", "build.gradle", "go.mod", "Cargo.toml",
            "src/main", "src/api", "cmd/server",
        ]
        if not any((project_root / m).is_file() for m in backend_markers):
            return "spa"

    # 2. 前后端混合
    frontend_dirs = ["frontend", "client", "web", "apps/web", "apps/client"]
    if any((project_root / d).is_dir() for d in frontend_dirs):
        return "frontend-backend"
    # 或者 monorepo 根目录有前端子 package
    if _has_frontend_package(project_root):
        return "frontend-backend"

    # 3. Java 后端
    if (project_root / "pom.xml").is_file() or (project_root / "build.gradle").is_file():
        return "backend-only"

    # 4. Python 后端
    python_markers = ["requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"]
    if any((project_root / m).is_file() for m in python_markers):
        # 排除纯前端项目（只有 requirements.txt 用于前端依赖）
        if (project_root / "package.json").is_file():
            # 同时存在？按前端目录判断
            pass
        return "backend-only"

    # 5. Go 后端
    if (project_root / "go.mod").is_file():
        return "backend-only"

    # 6. Rust 后端
    if (project_root / "Cargo.toml").is_file():
        return "backend-only"

    # 7. 微服务：多个 api/ 服务子目录
    api_dirs = list(project_root.glob("api/*/"))
    service_dirs = [d for d in api_dirs if d.is_dir() and (d / "openapi.yaml").is_file()]
    if len(service_dirs) >= 2:
        return "microservices"

    return "backend-only"


def _has_frontend_package(project_root: Path) -> bool:
    """检测 monorepo 中是否存在前端 package"""
    for pattern in ["packages/*/package.json", "apps/*/package.json"]:
        matches = list(project_root.glob(pattern))
        if matches:
            for pkg in matches:
                if _read_json_field(pkg, "name") in (
                    None, "", "undefined"
                ) and pkg.read_text(errors="ignore").strip() == "":
                    continue
                # 简单检查 scripts 中是否有 build/dev/test
                try:
                    import json as _json
                    data = _json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
                    scripts = data.get("scripts", {})
                    if any(k in scripts for k in ("dev", "build", "start", "test")):
                        return True
                except Exception:
                    continue
    return False


def _read_json_field(path: Path, field: str) -> str | None:
    try:
        import json
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return data.get(field)
    except Exception:
        return None


def get_recommended_runners(project_type: str) -> list[str]:
    """根据项目类型返回推荐的 runner 列表（按执行顺序）"""
    mapping: dict[str, list[str]] = {
        "backend-only":     ["openapi"],
        "frontend-backend": ["openapi", "playwright"],
        "spa":              ["playwright"],
        "microservices":    ["openapi"],
    }
    return mapping.get(project_type, ["openapi"])


# ─── CLI ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse, sys
    ap = argparse.ArgumentParser(description="项目类型检测")
    ap.add_argument("--project-root", default=None)
    args = ap.parse_args()

    root = Path(args.project_root) if args.project_root else None
    pt = detect_project_type(root)
    runners = get_recommended_runners(pt)
    print(f"project_type={pt}")
    print(f"recommended_runners={','.join(runners)}")
    sys.exit(0)

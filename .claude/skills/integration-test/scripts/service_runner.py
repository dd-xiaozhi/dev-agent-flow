"""被测服务启停管理：subprocess + health check + 超时强杀。

设计要点:
    - 优先读 generator handoff-artifact 的 service 段（YAML frontmatter）
    - 缺失则按 stack 默认推断（mvn spring-boot:run / uvicorn / npm run start）
    - 启动后轮询 health_url，超时（默认 30s）视为 ERROR，不计入 evaluator retry
    - try/finally 保证强杀；写 PID 到 .chatlabs/state/integration-test.pid 便于外部清理

Public API:
    ServiceConfig.from_handoff(handoff_path, stack) -> ServiceConfig | None
    ServiceConfig.default_for(stack) -> ServiceConfig | None
    run_service(cfg, project_root) -> ServiceHandle (context manager)
"""
from __future__ import annotations

import contextlib
import os
import re
import shlex
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

# 默认每个 stack 的服务启动配置
_STACK_DEFAULTS: dict[str, dict] = {
    "spring-boot": {
        "start_cmd": "mvn spring-boot:run",
        "health_url": "http://localhost:8080/actuator/health",
        "port": 8080,
    },
    "fastapi": {
        "start_cmd": "uvicorn app.main:app --port 8000",
        "health_url": "http://localhost:8000/health",
        "port": 8000,
    },
    "node-http": {
        "start_cmd": "npm run start",
        "health_url": "http://localhost:3000/health",
        "port": 3000,
    },
}


class ServiceStartError(RuntimeError):
    """服务启动 / 健康检查失败。"""


@dataclass
class ServiceConfig:
    """被测服务启动参数。"""

    start_cmd: str
    health_url: str
    port: int
    source: str  # "handoff" | "stack-default" | "explicit"

    @classmethod
    def default_for(cls, stack: str) -> "ServiceConfig | None":
        defaults = _STACK_DEFAULTS.get(stack)
        if not defaults:
            return None
        return cls(
            start_cmd=defaults["start_cmd"],
            health_url=defaults["health_url"],
            port=defaults["port"],
            source="stack-default",
        )

    @classmethod
    def from_handoff(cls, handoff_path: Path) -> "ServiceConfig | None":
        """从 handoff-artifact.md 的 frontmatter 读 service 段。

        期望格式:
            ---
            service:
              start_cmd: "mvn spring-boot:run"
              health_url: "http://localhost:8080/actuator/health"
              port: 8080
            ---
        """
        if not handoff_path.exists():
            return None
        text = handoff_path.read_text(encoding="utf-8", errors="ignore")
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if not m:
            return None
        fm = m.group(1)
        # 朴素 YAML 解析（避免引入 pyyaml 依赖；只支持本 schema）
        service_block = re.search(
            r"^service:\s*\n((?:[ \t]+\S.*\n?)+)", fm, re.MULTILINE
        )
        if not service_block:
            return None
        body = service_block.group(1)

        def _kv(key: str) -> str | None:
            mm = re.search(rf"^[ \t]+{key}:\s*(.+?)\s*$", body, re.MULTILINE)
            if not mm:
                return None
            val = mm.group(1).strip()
            if val.startswith(("'", '"')) and val.endswith(("'", '"')):
                val = val[1:-1]
            return val

        start_cmd = _kv("start_cmd")
        health_url = _kv("health_url")
        port_str = _kv("port")
        if not (start_cmd and health_url and port_str):
            return None
        try:
            port = int(port_str)
        except ValueError:
            return None
        return cls(
            start_cmd=start_cmd,
            health_url=health_url,
            port=port,
            source="handoff",
        )


@dataclass
class ServiceHandle:
    """服务运行期间的元数据快照。"""

    config: ServiceConfig
    pid: int
    started_at: str
    stopped_at: str | None = None


def _wait_for_health(url: str, timeout_s: int) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if 200 <= resp.status < 400:
                    return True
        except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, TimeoutError):
            pass
        time.sleep(1.0)
    return False


def _terminate(proc: subprocess.Popen, grace_s: int = 10) -> None:
    """SIGTERM → 等 grace 秒 → SIGKILL。"""
    if proc.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        else:
            proc.terminate()
    except (ProcessLookupError, PermissionError):
        return
    try:
        proc.wait(timeout=grace_s)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:
            proc.kill()
    except (ProcessLookupError, PermissionError):
        pass
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=5)


@contextlib.contextmanager
def run_service(
    cfg: ServiceConfig,
    project_root: Path,
    log_path: Path,
    pid_path: Path,
    health_timeout_s: int = 30,
) -> Iterator[ServiceHandle]:
    """以 context manager 方式启动服务，退出时强杀。

    Args:
        cfg: 服务启动配置
        project_root: 工作目录
        log_path: 子进程 stdout/stderr 重定向目标
        pid_path: PID 写入路径（外部脚本可读取做兜底清理）
        health_timeout_s: 健康检查超时（秒）

    Raises:
        ServiceStartError: 启动失败或健康检查超时
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.parent.mkdir(parents=True, exist_ok=True)

    # POSIX 上用进程组，便于一次性杀掉子进程树（mvn 会 fork）
    popen_kwargs: dict = {
        "cwd": str(project_root),
        "stdout": open(log_path, "w", encoding="utf-8"),
        "stderr": subprocess.STDOUT,
    }
    if os.name == "posix":
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(shlex.split(cfg.start_cmd), **popen_kwargs)
    pid_path.write_text(str(proc.pid), encoding="utf-8")
    started_at = datetime.now(timezone.utc).isoformat()
    handle = ServiceHandle(config=cfg, pid=proc.pid, started_at=started_at)

    try:
        if not _wait_for_health(cfg.health_url, health_timeout_s):
            raise ServiceStartError(
                f"health check timeout after {health_timeout_s}s: {cfg.health_url}"
            )
        yield handle
    finally:
        _terminate(proc)
        handle.stopped_at = datetime.now(timezone.utc).isoformat()
        with contextlib.suppress(OSError):
            pid_path.unlink()


def _main() -> int:
    """CLI 调试入口：从 handoff/stack 推 ServiceConfig 并打印。"""
    import argparse

    parser = argparse.ArgumentParser(description="探测被测服务启动配置")
    parser.add_argument("--handoff", type=Path, help="handoff-artifact.md 路径")
    parser.add_argument("--stack", help="技术栈名（用于降级默认）")
    args = parser.parse_args()

    cfg = None
    if args.handoff:
        cfg = ServiceConfig.from_handoff(args.handoff)
    if cfg is None and args.stack:
        cfg = ServiceConfig.default_for(args.stack)
    if cfg is None:
        print("未能解析出 ServiceConfig（handoff 缺失且 stack 不在默认表）", file=sys.stderr)
        return 2

    print(
        f"start_cmd={cfg.start_cmd}\n"
        f"health_url={cfg.health_url}\n"
        f"port={cfg.port}\n"
        f"source={cfg.source}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(_main())

#!/bin/bash
# gc-run.sh — GC CLI 包装
# 用法：
#   ./.claude/scripts/gc-run.sh         # dry_run（默认）
#   ./.claude/scripts/gc-run.sh --apply  # 执行清理（需确认）

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

python3 "$SCRIPT_DIR/gc.py" "$@"

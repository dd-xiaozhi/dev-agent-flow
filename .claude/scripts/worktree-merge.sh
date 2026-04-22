#!/bin/bash
# worktree-merge.sh — 合并 worktree 到 master
#
# 用法:
#   ./worktree-merge.sh <story_id> [--message "提交信息"] [--no-delete]
#
# 示例:
#   ./worktree-merge.sh STORY-001
#   ./worktree-merge.sh STORY-001 --message "feat: 新增用户反馈功能"
#   ./worktree-merge.sh STORY-001 --no-delete  # 合并后保留 worktree

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
CLAUDE_DIR="$PROJECT_DIR/.claude"
CHATLABS_DIR="$PROJECT_DIR/.chatlabs"
WORKTREE_MANAGER_FILE="$CHATLABS_DIR/worktree-manager.json"

# ── Colors ─────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ── Functions ────────────────────────────────────────────────────

usage() {
    echo "用法: $0 <story_id> [--message '提交信息'] [--no-delete]"
    echo ""
    echo "参数:"
    echo "  story_id      Story ID (如 STORY-001)"
    echo "  --message     合并提交信息 (可选)"
    echo "  --no-delete   合并后不删除 worktree (可选)"
    exit 1
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# 检查依赖
check_dependencies() {
    if ! command -v python3 &> /dev/null; then
        log_error "需要 python3，请先安装"
        exit 1
    fi
}

# 获取 worktree 信息
get_worktree_info() {
    local story_id="$1"
    python3 - "$story_id" "$WORKTREE_MANAGER_FILE" << 'PYTHON_SCRIPT'
import sys
import json

story_id = sys.argv[1]
manager_file = sys.argv[2]

try:
    with open(manager_file, 'r') as f:
        data = json.load(f)

    if story_id in data.get('worktrees', {}):
        info = data['worktrees'][story_id]
        print(json.dumps(info))
    else:
        print("{}")
except Exception as e:
    print("{}", file=sys.stderr)
    sys.exit(1)
PYTHON_SCRIPT
}

# 检查 generator:all-done 事件
check_completion() {
    local worktree_path="$1"
    local events_file="$worktree_path/.chatlabs/state/events.jsonl"

    if [[ -f "$events_file" ]]; then
        if grep -q "generator:all-done" "$events_file"; then
            return 0
        fi
    fi
    return 1
}

# 执行合并
do_merge() {
    local story_id="$1"
    local commit_message="$2"
    local delete_after="$3"
    local main_branch="$4"
    local branch="$5"
    local worktree_path="$6"

    cd "$PROJECT_DIR"

    # 切换到 main branch
    log_info "切换到 $main_branch..."
    git checkout "$main_branch"

    # 合并分支
    log_info "合并 $branch 到 $main_branch..."
    if git merge --no-ff -m "$commit_message" "$branch"; then
        log_info "合并成功"
    else
        log_error "合并失败，请手动解决冲突"
        exit 1
    fi

    # 更新 worktree-manager.json
    log_info "更新 worktree-manager.json..."
    python3 - "$story_id" "$WORKTREE_MANAGER_FILE" << 'PYTHON_SCRIPT'
import sys
import json
from datetime import datetime, timezone

story_id = sys.argv[1]
manager_file = sys.argv[2]

with open(manager_file, 'r') as f:
    data = json.load(f)

if story_id in data.get('worktrees', {}):
    data['worktrees'][story_id]['status'] = 'merged'
    data['worktrees'][story_id]['merged'] = True
    data['worktrees'][story_id]['merged_at'] = datetime.now(timezone.utc).isoformat()

    with open(manager_file, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("updated")
else:
    print("not_found")
PYTHON_SCRIPT

    # 删除 worktree 和分支
    if [[ "$delete_after" == "true" ]]; then
        log_info "删除 worktree 目录..."
        rm -rf "$worktree_path"

        log_info "删除分支..."
        git branch -D "$branch" 2>/dev/null || true
    fi
}

# ── Main ──────────────────────────────────────────────────────────

main() {
    # 解析参数
    STORY_ID=""
    COMMIT_MESSAGE=""
    DELETE_AFTER="true"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --message|-m)
                COMMIT_MESSAGE="$2"
                shift 2
                ;;
            --no-delete)
                DELETE_AFTER="false"
                shift
                ;;
            -h|--help)
                usage
                ;;
            -*)
                log_error "未知参数: $1"
                usage
                ;;
            *)
                if [[ -z "$STORY_ID" ]]; then
                    STORY_ID="$1"
                else
                    log_error "太多位置参数"
                    usage
                fi
                shift
                ;;
        esac
    done

    # 检查必填参数
    if [[ -z "$STORY_ID" ]]; then
        log_error "缺少 story_id"
        usage
    fi

    check_dependencies

    # 获取 worktree 信息
    WORKTREE_INFO=$(get_worktree_info "$STORY_ID")

    if [[ -z "$WORKTREE_INFO" ]] || [[ "$WORKTREE_INFO" == "{}" ]]; then
        log_error "未找到 story_id=$STORY_ID 的 worktree"
        exit 1
    fi

    # 解析 JSON
    WORKTREE_PATH=$(echo "$WORKTREE_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin)['path'])")
    BRANCH=$(echo "$WORKTREE_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin)['branch'])")
    MAIN_BRANCH=$(python3 -c "import json; print(json.load(open('$WORKTREE_MANAGER_FILE'))['main_branch'])")
    DESCRIPTION=$(echo "$WORKTREE_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin).get('description') or 'worktree')" 2>/dev/null || echo "worktree")

    # 构建 worktree 绝对路径
    WORKTREE_ABS_PATH="$PROJECT_DIR/$WORKTREE_PATH"

    # 检查完成状态
    log_info "检查完成状态..."
    if check_completion "$WORKTREE_ABS_PATH"; then
        log_info "检测到 generator:all-done 事件"
    else
        log_warn "未检测到 generator:all-done 事件，继续合并..."
    fi

    # 设置默认提交信息
    if [[ -z "$COMMIT_MESSAGE" ]]; then
        COMMIT_MESSAGE="Merge $STORY_ID ($DESCRIPTION)"
    fi

    # 执行合并
    log_info "═══════════════════════════════════════════════════════════"
    log_info "  合并 $STORY_ID 到 $MAIN_BRANCH"
    log_info "═══════════════════════════════════════════════════════════"
    log_info "  Story:      $STORY_ID"
    log_info "  分支:       $BRANCH"
    log_info "  路径:       $WORKTREE_ABS_PATH"
    log_info "  提交信息:   $COMMIT_MESSAGE"
    log_info "  删除 worktree: $DELETE_AFTER"
    log_info "═══════════════════════════════════════════════════════════"

    do_merge "$STORY_ID" "$COMMIT_MESSAGE" "$DELETE_AFTER" "$MAIN_BRANCH" "$BRANCH" "$WORKTREE_ABS_PATH"

    echo ""
    log_info "✅ $STORY_ID 已合并到 $MAIN_BRANCH"
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "  已完成:"
    echo "  - 提交合并到 $MAIN_BRANCH"
    if [[ "$DELETE_AFTER" == "true" ]]; then
        echo "  - worktree 目录已删除"
        echo "  - 分支 $BRANCH 已删除"
    else
        echo "  - worktree 目录保留在 $WORKTREE_ABS_PATH"
    fi
    echo "═══════════════════════════════════════════════════════════"
}

main "$@"

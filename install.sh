#!/usr/bin/env bash
# =============================================================================
# install.sh — ChatLabs Dev-Flow Harness 一键安装脚本
#
# 支持两种模式：
#   1. 原目录安装（./install.sh）      — 验证当前 harness 完整性 + 设置权限
#   2. 模板安装（./install.sh <目标>） — 将 harness 复制到目标项目
#
# MCP servers 不在安装范围内，由各项目自行配置 .mcp.json
# =============================================================================

set -euo pipefail

HARNESS_VERSION="1.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 需要检查的顶层目录
REQUIRED_DIRS=(
    ".claude/agents"
    ".claude/commands"
    ".claude/hooks"
    ".claude/scripts"
    ".claude/skills"
    ".claude/templates"
    "docs"
)

# .claude/ 下的核心文件
REQUIRED_CLAUDE_FILES=(
    ".claude/settings.json"
    ".claude/settings.local.json"
)

# scripts 目录下需要执行权限的文件（ glob 匹配）
SCRIPT_PATTERNS=(
    ".claude/scripts/*.sh"
    ".claude/scripts/*.py"
)

# =============================================================================
# 颜色输出
# =============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[FAIL]${NC}  $*" >&2; exit 1; }

# =============================================================================
# 检测 Claude Code 是否已安装
# =============================================================================
check_claude_code() {
    info "检测 Claude Code..."

    if command -v claude &>/dev/null; then
        local version
        version=$(claude --version 2>/dev/null | head -1 || echo "unknown")
        success "Claude Code 已安装: $version"
        return 0
    fi

    error "Claude Code 未安装。请先安装：https://docs.anthropic.com/en/docs/claude-code/setup"
}

# =============================================================================
# 验证 harness 目录结构完整性
# =============================================================================
verify_harness_structure() {
    info "验证 harness 目录结构..."

    local missing=0
    for dir in "${REQUIRED_DIRS[@]}"; do
        if [[ ! -d "$SCRIPT_DIR/$dir" ]]; then
            error "缺少目录: $dir"
            ((missing++))
        fi
    done

    for file in "${REQUIRED_CLAUDE_FILES[@]}"; do
        if [[ ! -f "$SCRIPT_DIR/$file" ]]; then
            warn "缺少文件: $file (可能是可选的本地配置)"
        fi
    done

    # 检查 agents
    local agent_count
    agent_count=$(find "$SCRIPT_DIR/.claude/agents" -maxdepth 1 -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    if (( agent_count < 5 )); then
        warn "agents 目录文件数异常 (期望 ≥5, 实际 $agent_count)"
    fi

    # 检查 commands
    local cmd_count
    cmd_count=$(find "$SCRIPT_DIR/.claude/commands" -maxdepth 1 -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    if (( cmd_count < 10 )); then
        warn "commands 目录文件数异常 (期望 ≥10, 实际 $cmd_count)"
    fi

    # 检查 skills
    local skill_count
    skill_count=$(find "$SCRIPT_DIR/.claude/skills" -maxdepth 1 -type d 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')
    if (( skill_count < 5 )); then
        warn "skills 目录文件数异常 (期望 ≥5, 实际 $skill_count)"
    fi

    # 检查 hooks
    local hook_count
    hook_count=$(find "$SCRIPT_DIR/.claude/hooks" -maxdepth 1 \( -name "*.py" -o -name "*.sh" \) 2>/dev/null | wc -l | tr -d ' ')
    if (( hook_count < 3 )); then
        warn "hooks 目录文件数异常 (期望 ≥3, 实际 $hook_count)"
    fi

    # 检查 scripts
    if [[ ! -f "$SCRIPT_DIR/.claude/scripts/paths.py" ]]; then
        error "缺少核心脚本: .claude/scripts/paths.py"
    fi

    if (( missing > 0 )); then
        error "目录结构不完整，缺失 $missing 项"
    fi

    success "目录结构验证通过"
}

# =============================================================================
# 设置文件权限
# =============================================================================
set_permissions() {
    info "设置脚本执行权限..."

    for pattern in "${SCRIPT_PATTERNS[@]}"; do
        for file in $SCRIPT_DIR/$pattern; do
            [[ -e "$file" ]] || continue
            if [[ ! -x "$file" ]]; then
                chmod +x "$file" 2>/dev/null && success "设置执行权限: ${file##*/}" || warn "无法设置执行权限: $file"
            fi
        done
    done

    success "权限设置完成"
}

# =============================================================================
# 验证 Python 依赖（scripts 所需）
# =============================================================================
check_python_deps() {
    info "检查 Python 依赖..."

    if ! command -v python3 &>/dev/null; then
        warn "python3 未找到，部分脚本可能无法运行"
        return 0
    fi

    # 检查 paths.py 是否可导入（间接验证语法）
    if python3 -c "import sys; sys.path.insert(0, '.claude/scripts'); import paths" 2>/dev/null; then
        success "Python 路径模块正常"
    else
        warn "Python 路径模块导入失败，请检查 .claude/scripts/paths.py 语法"
    fi
}

# =============================================================================
# 显示安装摘要
# =============================================================================
show_summary() {
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "  ChatLabs Dev-Flow Harness v${HARNESS_VERSION}  安装完成"
    echo "════════════════════════════════════════════════════════════════"
    echo ""
    echo "  Agents   : $(find "$SCRIPT_DIR/.claude/agents" -maxdepth 1 -name "*.md" 2>/dev/null | wc -l | tr -d ' ') 个"
    echo "  Commands : $(find "$SCRIPT_DIR/.claude/commands" -maxdepth 1 -name "*.md" 2>/dev/null | wc -l | tr -d ' ') 个"
    echo "  Skills   : $(find "$SCRIPT_DIR/.claude/skills" -maxdepth 1 -type d 2>/dev/null | tail -n +2 | wc -l | tr -d ' ') 个"
    echo "  Hooks    : $(find "$SCRIPT_DIR/.claude/hooks" -maxdepth 1 \( -name "*.py" -o -name "*.sh" \) 2>/dev/null | wc -l | tr -d ' ') 个"
    echo "  Scripts  : $(find "$SCRIPT_DIR/.claude/scripts" -maxdepth 1 \( -name "*.py" -o -name "*.sh" \) 2>/dev/null | wc -l | tr -d ' ') 个"
    echo ""
    echo "  快速开始："
    echo "    /start-dev-flow           # 智能入口，自动识别意图"
    echo ""
    echo "  注意：MCP servers 请在项目中单独配置 .mcp.json"
    echo "════════════════════════════════════════════════════════════════"
    echo ""
}

# =============================================================================
# 模板安装模式：复制到目标项目
# =============================================================================
install_to_target() {
    local target_dir="$1"

    info "目标项目: $target_dir"

    if [[ ! -d "$target_dir" ]]; then
        if [[ -t 0 ]]; then
            read -rp "目录不存在，是否创建? [y/N] " confirm
            [[ "$confirm" =~ ^[Yy]$ ]] || { info "取消安装"; exit 0; }
        else
            info "目录不存在，自动创建: $target_dir"
        fi
        mkdir -p "$target_dir"
    fi

    if [[ -d "$target_dir/.claude" ]]; then
        warn "目标目录已存在 .claude/，将保留现有配置"
        if [[ -t 0 ]]; then
            read -rp "是否覆盖? [y/N] " confirm
            [[ "$confirm" =~ ^[Yy]$ ]] || { info "取消安装"; exit 0; }
        else
            warn "跳过覆盖（非交互模式）"
            info "取消安装"
            exit 0
        fi
    fi

    info "复制 harness 文件..."

    # rsync 排除项：本地配置 + TAPD 初始化命令（各项目按需创建）
    rsync -av \
        --exclude='__pycache__' \
        --exclude='.DS_Store' \
        --exclude='settings.local.json' \
        --exclude='.current_task' \
        --exclude='.gc_last_run' \
        --exclude='.contract_hash' \
        --exclude='hooks/__pycache__' \
        --exclude='commands/__pycache__' \
        --exclude='scripts/__pycache__' \
        --exclude='tapd-consensus-push.md' \
        --exclude='tapd-consensus-fetch.md' \
        --exclude='tapd-init.md' \
        --exclude='tapd-story-start.md' \
        --exclude='tapd-subtask-close.md' \
        --exclude='tapd-subtask-emit.md' \
        --exclude='tapd-subtask-reopen.md' \
        --exclude='tapd-ticket-sync.md' \
        "$SCRIPT_DIR/.claude/" "$target_dir/.claude/"

    rsync -av \
        --exclude='.DS_Store' \
        "$SCRIPT_DIR/docs/" "$target_dir/docs/"

    # 创建 README.md 片段供追加
    cat > "$target_dir/.claude-README-INSERT.md" << 'INSERT_EOF'

---
## ChatLabs Dev-Flow Harness

本项目集成了 ChatLabs Dev-Flow Harness。
详细文档请参考 [harness 仓库](https://github.com/your-org/chatlabs-dev-flow)。

常用命令：
- `/start-dev-flow` — 启动主流程
- `/tapd-init` — 配置 TAPD
INSERT_EOF

    success "安装完成: $target_dir"
    info "请检查 $target_dir/.claude/settings.local.json 并按需调整"
}

# =============================================================================
# 主流程
# =============================================================================
main() {
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║    ChatLabs Dev-Flow Harness 安装脚本  v${HARNESS_VERSION}       ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""

    # 参数处理
    if [[ $# -gt 0 ]]; then
        if [[ "$1" == "-h" || "$1" == "--help" ]]; then
            echo "用法: $0 [目标目录]"
            echo ""
            echo "  无参数     — 验证当前目录 harness 完整性"
            echo "  <目标目录> — 将 harness 复制到目标项目"
            exit 0
        fi
        install_to_target "$1"
        exit 0
    fi

    # 原目录安装模式
    check_claude_code
    verify_harness_structure
    set_permissions
    check_python_deps
    show_summary
}

main "$@"

#!/bin/bash
# danger-block — 拦截破坏性 Bash 命令
# 事件：PreToolUse (matcher: Bash)
# 依据：AGENTS.md 禁止清单、~/.claude/CLAUDE.md 删除操作确认规则
#
# 原则：黑名单最小集（KISS / YAGNI）；命中即 exit 2 block
# 扩展：新增规则追加到 patterns 数组即可

set -u

input=$(cat)

# 用 python3 解析 JSON（本仓已依赖 python3，避免 jq 硬依赖）
cmd=$(python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('command', ''))
except Exception:
    pass
" <<<"$input" 2>/dev/null)

if [ -z "$cmd" ]; then
    exit 0
fi

# 危险命令黑名单（ERE 正则，大小写不敏感）
patterns=(
    'rm[[:space:]]+-rf[[:space:]]+/([[:space:]]|$)'
    'rm[[:space:]]+-rf[[:space:]]+/\*'
    'rm[[:space:]]+-rf[[:space:]]+~'
    'rm[[:space:]]+-rf[[:space:]]+\$HOME'
    'git[[:space:]]+reset[[:space:]]+--hard'
    'git[[:space:]]+push[[:space:]]+(-f|--force)'
    'git[[:space:]]+clean[[:space:]]+-[a-z]*f'
    'git[[:space:]]+branch[[:space:]]+-D'
    'git[[:space:]]+commit[[:space:]]+.*--no-verify'
    'DROP[[:space:]]+(TABLE|DATABASE|SCHEMA)'
    'TRUNCATE[[:space:]]+TABLE'
    'kill[[:space:]]+-9[[:space:]]+1([[:space:]]|$)'
    'mkfs\.'
    'dd[[:space:]]+if=.*of=/dev/'
    ':\(\)[[:space:]]*\{.*\}[[:space:]]*;'
    '>[[:space:]]*/dev/sda'
)

for p in "${patterns[@]}"; do
    if echo "$cmd" | grep -Eqi "$p"; then
        {
            echo "[danger-block] 命令被拦截"
            echo "  命令：$cmd"
            echo "  规则：$p"
            echo "→ 此类破坏性操作需先向用户输出风险提示方案并获得明确确认。"
            echo "→ 依据：AGENTS.md 禁止清单、~/.claude/CLAUDE.md 删除操作确认规则"
        } >&2
        exit 2
    fi
done

exit 0

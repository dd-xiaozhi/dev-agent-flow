#!/usr/bin/env bash
# contract-test 统一入口脚本
# 依据：skills/contract-test/SKILL.md §4（适配器插件架构）
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADAPTERS_DIR="$SCRIPT_DIR/adapters"
OUTPUT_DIR="${OUTPUT_DIR:-./reports/verdicts}"
mkdir -p "$OUTPUT_DIR"

usage() {
    cat <<EOF
Usage: $0 --openapi <path> --base-url <url> [--adapter <name>] [--output <path>]

选项：
  --openapi   OpenAPI spec 路径（必需）
  --base-url  被测服务 base URL（必需）
  --adapter   适配器名：rest-assured | schemathesis（自动检测如未指定）
  --output    verdict 输出路径（默认 reports/verdicts/<ts>.json）

示例：
  $0 --openapi openapi.yaml --base-url http://localhost:8080
  $0 --openapi openapi.yaml --base-url http://localhost:8000 --adapter schemathesis
EOF
    exit 1
}

OPENAPI=""
BASE_URL=""
ADAPTER=""
OUTPUT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --openapi)  OPENAPI="$2"; shift 2 ;;
        --base-url) BASE_URL="$2"; shift 2 ;;
        --adapter)  ADAPTER="$2"; shift 2 ;;
        --output)   OUTPUT="$2"; shift 2 ;;
        -h|--help)  usage ;;
        *)          echo "未知参数: $1"; usage ;;
    esac
done

[[ -z "$OPENAPI" || -z "$BASE_URL" ]] && usage

# 生成 output 路径
if [[ -z "$OUTPUT" ]]; then
    TS=$(date +%Y%m%dT%H%M%S)
    OUTPUT="$OUTPUT_DIR/$TS.json"
fi

# 自动检测 adapter（按 openapi.yaml 内容推断）
if [[ -z "$ADAPTER" ]]; then
    if grep -q "rest-assured\|spring-boot\|junit" "$OPENAPI" 2>/dev/null; then
        ADAPTER="rest-assured"
    elif grep -q "fastapi\|python" "$OPENAPI" 2>/dev/null; then
        ADAPTER="schemathesis"
    else
        # 降级：检查 pom.xml 或 requirements.txt
        if [[ -f "${OPENAPI%/*}/pom.xml" ]]; then
            ADAPTER="rest-assured"
        elif [[ -f "${OPENAPI%/*}/requirements.txt" ]]; then
            ADAPTER="schemathesis"
        else
            echo "ERROR: 无法推断 adapter，请显式指定 --adapter" >&2
            exit 2
        fi
    fi
fi

ADAPTER_SCRIPT="$ADAPTERS_DIR/${ADAPTER}-runner.sh"
if [[ ! -x "$ADAPTER_SCRIPT" ]]; then
    echo "ERROR: adapter '$ADAPTER' 未找到或无执行权限: $ADAPTER_SCRIPT" >&2
    echo "可用 adapter：$(ls "$ADAPTERS_DIR"/*.sh 2>/dev/null | xargs -I{} basename {} .sh | tr '\n' ' ')" >&2
    exit 2
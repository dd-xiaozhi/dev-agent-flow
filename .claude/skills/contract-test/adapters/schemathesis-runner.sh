#!/usr/bin/env bash
# schemathesis adapter — Python / FastAPI 契约测试 runner
# 依据：skills/contract-test/SKILL.md；examples/hello-python/ 配套
set -e

OPENAPI_URL=""
BASE_URL=""
OUTPUT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --openapi)  OPENAPI_URL="$2"; shift 2 ;;
        --base-url) BASE_URL="$2"; shift 2 ;;
        --output)   OUTPUT="$2"; shift 2 ;;
        *)          shift ;;
    esac
done

[[ -z "$BASE_URL" ]] && { echo "ERROR: --base-url 必需"; exit 2; }

# schemathesis 读 live OpenAPI endpoint
OPENAPI_ENDPOINT="${BASE_URL}/openapi.json"

# 检查服务可达
if ! curl -s --max-time 5 "$OPENAPI_ENDPOINT" > /dev/null 2>&1; then
    echo "ERROR: 服务不可达: $OPENAPI_ENDPOINT" >&2
    exit 2
fi

echo "[schemathesis] base-url=$BASE_URL openapi=$OPENAPI_ENDPOINT"

# 运行 schemathesis（property-based testing from live OpenAPI）
# --exitcode-ci：失败时 exit 1
# --verbose：输出每个测试结果
OUTPUT_TEXT=$(schemathesis run \
    "$OPENAPI_ENDPOINT" \
    --verbose \
    --exitcode-ci \
    2>&1) || SCHEMESIS_EXIT=$?

SCHEMESIS_EXIT=${SCHEMESIS_EXIT:-0}

# 解析通过/失败数（从 stdout 提取）
PASSED=$(echo "$OUTPUT_TEXT" | grep -c "PASS" || true)
FAILED=$(echo "$OUTPUT_TEXT" | grep -c "FAIL" || true)

mkdir -p "$(dirname "$OUTPUT")"
cat > "$OUTPUT" <<EOF
{
  "ts": "$(date -Iseconds)",
  "source": "contract-test",
  "adapter": "schemathesis",
  "verdict": "$( [ $SCHEMESIS_EXIT -eq 0 ] && echo PASS || echo FAIL )",
  "openapi_endpoint": "$OPENAPI_ENDPOINT",
  "base_url": "$BASE_URL",
  "test_count": $((PASSED + FAILED)),
  "passed": $PASSED,
  "failed": $FAILED,
  "raw_output": $(echo "$OUTPUT_TEXT" | head -50 | python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))"),
  "failures": [],
  "contract_violations": [],
  "next_action": "$( [ $SCHEMESIS_EXIT -eq 0 ] && echo '交付' || echo '修复后重跑' )"
}
EOF

echo "[schemathesis] verdict=$( [ $SCHEMESIS_EXIT -eq 0 ] && echo PASS || echo FAIL ) passed=$PASSED failed=$FAILED"
echo "verdict saved: $OUTPUT"
exit $SCHEMESIS_EXIT

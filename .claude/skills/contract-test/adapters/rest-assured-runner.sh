#!/usr/bin/env bash
# rest-assured adapter — Java / SpringBoot 契约测试 runner
# 依据：skills/contract-test/SKILL.md；examples/hello-java/ 配套
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"

OPENAPI=""
BASE_URL=""
OUTPUT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --openapi)  OPENAPI="$2"; shift 2 ;;
        --base-url) BASE_URL="$2"; shift 2 ;;
        --output)   OUTPUT="$2"; shift 2 ;;
        *)          shift ;;
    esac
done

[[ -z "$OPENAPI" || -z "$BASE_URL" ]] && { echo "ERROR: --openapi 和 --base-url 必需"; exit 2; }

# 找 Maven 项目根（向上找 pom.xml）
Maven_DIR="$OPENAPI"
while [[ "$Maven_DIR" != "/" ]]; do
    Maven_DIR="$(dirname "$Maven_DIR")"
    if [[ -f "$Maven_DIR/pom.xml" ]]; then
        break
    fi
done

if [[ ! -f "$Maven_DIR/pom.xml" ]]; then
    echo "ERROR: 找不到 pom.xml（Maven 项目）" >&2
    exit 2
fi

echo "[rest-assured] project=$Maven_DIR base-url=$BASE_URL"

cd "$Maven_DIR"

# 运行契约测试（跳过需要服务的集成测试，生产环境用 test  profile）
mvn test \
    -Dtest=ContractTest \
    -DbaseUrl="$BASE_URL" \
    -DfailIfNoTests=false \
    -q 2>&1 | tail -5

TEST_EXIT=$?

# 解析测试结果
PASSED=$(find target/surefire-reports -name "*.txt" 2>/dev/null | xargs grep -c "Tests run:" 2>/dev/null | awk -F: '{sum+=$2} END{print sum+0}')
FAILED=$(find target/surefire-reports -name "*.txt" 2>/dev/null | xargs grep -c "FAILURE" 2>/dev/null | awk -F: '{sum+=$2} END{print sum+0}')

# 写入 verdict
mkdir -p "$(dirname "$OUTPUT")"
cat > "$OUTPUT" <<EOF
{
  "ts": "$(date -Iseconds)",
  "source": "contract-test",
  "adapter": "rest-assured",
  "verdict": "$( [ $TEST_EXIT -eq 0 ] && echo PASS || echo FAIL )",
  "openapi": "$OPENAPI",
  "base_url": "$BASE_URL",
  "test_count": $((PASSED + FAILED)),
  "passed": $PASSED,
  "failed": $FAILED,
  "failures": [],
  "contract_violations": [],
  "next_action": "$( [ $TEST_EXIT -eq 0 ] && echo '交付' || echo '修复后重跑' )"
}
EOF

echo "[rest-assured] verdict=$( [ $TEST_EXIT -eq 0 ] && echo PASS || echo FAIL ) passed=$PASSED failed=$FAILED"
echo "verdict saved: $OUTPUT"
exit $TEST_EXIT

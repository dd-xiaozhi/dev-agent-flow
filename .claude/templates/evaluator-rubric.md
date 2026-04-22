# Evaluator 验收评分标准

> 给 evaluator agent 看的验收细则。
> 文件置于 `.chatlabs/stories/<story-id>/evaluator-rubric.md`（由 Evaluator 根据 contract.md 动态生成）。

---

## 验收通过标准

| 维度 | 标准 | 检查方式 |
|------|------|---------|
| OpenAPI 一致性 | 100% 字段匹配，无漂移 | schemathesis |
| 状态码合规 | 4xx/5xx 场景覆盖正确 | rest-assured |
| 响应格式 | 与 openapi.yaml schema 一致 | schemathesis |
| 错误消息 | 符合 contract.md §4 业务规则 | 断言检查 |

---

## Verdict 格式说明

```json
{
  "verdict": "PASS | FAIL",
  "case_id": "STORY-XXX/CASE-01",
  "passed_acs": ["AC-001", "AC-002"],
  "failed_acs": [],
  "failures": [],
  "summary": "..."
}
```

### failures 字段格式

每个 failure 必须包含：

```json
{
  "ac": "AC-003",
  "description": "实际响应与 schema 不一致",
  "actual": "{\"id\": 1}",
  "expected": "{\"id\": \"1\"}",
  "curl": "curl -X POST http://localhost:8080/api/v1/xxx -H 'Content-Type: application/json' -d '{}'",
  "severity": "critical | major | minor"
}
```

---

## AC → 测试用例映射

| AC | 测试用例 | 覆盖方式 |
|----|---------|---------|
| AC-001 | 创建成功返回 201 | schemathesis |
| AC-002 | 重复提交返回 409 | rest-assured |
| ... | ... | ... |

---

## 评分维度权重

| 维度 | 权重 | 说明 |
|------|------|------|
| OpenAPI 一致性 | 40% | 跨端契约核心 |
| 状态码合规 | 20% | HTTP 语义 |
| 响应格式 | 20% | schema 一致 |
| 业务规则 | 20% | contract.md §4 |

---

## 关联

- 契约文档：`.chatlabs/stories/<story-id>/contract.md`
- OpenAPI 定义：`.chatlabs/stories/<story-id>/openapi.yaml`
- Sprint Contract：`.chatlabs/stories/<story-id>/sprint-contract.md`
---
name: contract-test
description: 对已实现的 HTTP API 运行 OpenAPI 契约测试，产出 Evaluator verdict。支持多 adapter（rest-assured、schemathesis）。用于 Generator 交付后的独立验收环节，或手动触发验证。触发关键词：契约测试、contract test、run evaluator、验收测试、openapi 测试。
---

# Contract Test — HTTP 契约测试统一入口

## 架构：适配器插件模式

```
contract-test skill
    ├── run.py  ← 统一入口，按 --adapter 分发
    ├── adapters/
    │   ├── __init__.py
    │   ├── rest_assured_runner.py   ← Java / SpringBoot（CLI 名：rest-assured）
    │   ├── schemathesis_runner.py   ← Python / FastAPI（CLI 名：schemathesis）
    │   └── ...                      ← 按需扩展
    └── templates/
        └── verdict.json
```

添加新 adapter：
1. 新建 `adapters/<name>_runner.py`，实现 `run(openapi, base_url, output) -> int`
2. 在 `run.py` 的 `ADAPTER_MODULES` 字典登记：`"<cli-name>": "<name>_runner"`

## 使用方式

### 基础用法
```bash
# 自动检测 adapter（按 openapi.yaml 内容推断）
python .claude/skills/contract-test/run.py \
    --openapi <openapi.yaml> \
    --base-url http://localhost:8080 \
    --output reports/verdicts/<ts>.json

# 显式指定 adapter
python .claude/skills/contract-test/run.py \
    --adapter rest-assured \
    --openapi examples/hello-java/src/main/resources/openapi.yaml \
    --base-url http://localhost:8080
```

### Claude Code 内调用
```
/contract-test --openapi <path> --base-url <url> [--adapter rest-assured|schemathesis]
```

## Adapter 接口约定

每个 adapter runner 必须实现：

```python
# adapters/<name>_runner.py
def run(openapi: str, base_url: str, output: str) -> int:
    """
    运行契约测试，写 verdict JSON 到 output 路径。
    返回退出码：0=pass, 1=fail, 2=error
    """
```

同时提供 CLI 入口，支持参数 `--openapi`、`--base-url`、`--output`，便于独立调试。

**输出**：写入 verdict JSON 到 `--output` 路径，格式见 `templates/verdict.json`。

## 内置 Adapter

### rest-assured（Java / SpringBoot）

- **前置**：Java 17+，`mvn` 可用
- **测试类**：`src/test/java/.../ContractTest.java`
- **命令**：`mvn test -Dtest=ContractTest -DbaseUrl=<url>`
- **报告**：`target/surefire-reports/*.xml`

### schemathesis（Python / FastAPI）

- **前置**：`schemathesis` 已安装，服务已启动
- **命令**：`schemathesis run <base-url>/openapi.json --verbose --output=text`
- **报告**：stdout + JSON 报告

## Verdict 格式

```json
{
  "ts": "2026-04-17T15:00:00+08:00",
  "source": "contract-test",
  "adapter": "<name>",
  "verdict": "PASS | FAIL",
  "openapi": "<openapi-path>",
  "base_url": "<url>",
  "test_count": 5,
  "passed": 4,
  "failed": 1,
  "failures": [
    {
      "test": "AC-2: createUser_missingEmail_returns400",
      "curl": "curl -X POST http://localhost:8080/api/users -d '{}' -H 'Content-Type: application/json'",
      "expected": "status 400",
      "actual": "status 500",
      "fix": "修复 UserController.create 对空 email 的处理，返回 400 而非 500"
    }
  ],
  "contract_violations": [],
  "next_action": "交付 | 修复后重跑"
}
```

## 质量门禁

- **任何 adapter exit != 0** → 整体 FAIL
- **无 `openapi.yaml`** → 拒绝运行（fitness 规则）
- **被测服务不可达** → 明确报错，不返回假通过

## 与 Evaluator Agent 的关系

Evaluator agent 内部调用本 skill：
```
evaluator → contract-test skill → adapter runner → verdict.json → evaluator verdict
```

本 skill 只负责运行测试和产 verdict，评分和 verdict 格式化由 Evaluator agent 完成。

## 关联

- Agent：`agents/evaluator.md`
- 模板：`templates/evaluator-rubric.md`

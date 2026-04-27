---
name: contract-test
description: |
  智能契约测试策略路由。根据项目类型自动选择最优测试方式：
  - 纯后端 → OpenAPI Schema 验证（schemathesis / rest-assured）
  - 前后端 → OpenAPI + Playwright E2E
  - 纯前端 SPA → Playwright E2E
  产出结构化 verdict JSON，供 Evaluator agent 评分。
  触发关键词：契约测试、contract test、run evaluator、验收测试、openapi 测试、e2e 测试、端到端测试。
---

# Contract Test — 智能契约测试策略

## 核心变化

- **命名修正**：从"契约测试"明确为"API + E2E 智能策略路由"
- **runner 替换 adapter**：按测试类型（OpenAPI / Playwright）而非语言（schemathesis / rest-assured）组织
- **自动检测**：根据项目类型自动选择 runner，无需手动指定
- **多 runner 汇总**：前后端项目自动运行多个 runner，合并 verdict

## 架构

```
contract-test skill
    ├── run.py                    ← 智能路由入口（策略选择器）
    ├── detectors/
    │   └── project_type.py       ← 项目类型检测
    ├── runners/
    │   ├── __init__.py
    │   ├── openapi_runner.py     ← HTTP API Schema 验证（内部桥接 schemathesis/rest-assured）
    │   └── playwright_runner.py  ← E2E 端到端测试
    └── adapters/                 ← 保留，向后兼容 openapi_runner 内部调用
        ├── schemathesis_runner.py
        └── rest_assured_runner.py
```

## 项目类型 → Runner 映射

| 项目类型 | 检测依据 | 运行的 Runner |
|----------|---------|--------------|
| `backend-only` | pom.xml / requirements.txt / go.mod / Cargo.toml | openapi |
| `frontend-backend` | 存在 frontend/ 或 monorepo 有前端子 package | openapi + playwright |
| `spa` | 根目录 package.json 且无后端根目录 | playwright |
| `microservices` | 多个 api/*/ 子目录含 openapi.yaml | openapi |

## 使用方式

### 基础用法（自动检测）
```bash
# 自动检测项目类型 + 选择 runner
python .claude/skills/contract-test/run.py \
    --openapi <openapi.yaml> \
    --base-url http://localhost:8080

# 仅检测项目类型，不运行测试
python .claude/skills/contract-test/run.py --detect-only

# 手动指定 runner
python .claude/skills/contract-test/run.py \
    --openapi <path> --base-url <url> --runner openapi

# 运行所有推荐 runner（忽略自动推断）
python .claude/skills/contract-test/run.py \
    --openapi <path> --base-url <url> --runner all
```

### Claude Code 内调用
```
/contract-test --openapi <path> --base-url <url> [--runner openapi|playwright|all]
```

## Runner 接口约定

每个 runner 必须实现：

```python
# runners/<name>_runner.py
def run(openapi: str, base_url: str, output: str) -> int:
    """
    运行测试，写 verdict JSON 到 output 路径。
    返回退出码：0=pass, 1=fail, 2=error
    """
```

**输出**：写入 verdict JSON 到 `--output` 路径。

## Verdict 格式

### 单个 Runner Verdict
```json
{
  "ts": "2026-04-17T15:00:00+08:00",
  "source": "contract-test",
  "runner": "openapi | playwright",
  "verdict": "PASS | FAIL | ERROR",
  "openapi": "<openapi-path>",
  "base_url": "<url>",
  "test_count": 10,
  "passed": 9,
  "failed": 1,
  "failures": [
    {
      "test": "AC-2: createUser_missingEmail_returns400",
      "error": "expected status 400, got 500",
      "fix": "修复 UserController.create 对空 email 的处理"
    }
  ],
  "contract_violations": [],
  "next_action": "交付 | 修复后重跑"
}
```

### 汇总 Verdict（多 Runner）
```json
{
  "ts": "2026-04-17T15:00:00+08:00",
  "source": "contract-test",
  "strategy": "multi-runner",
  "verdict": "PASS | FAIL",
  "project_type": "frontend-backend",
  "runners": ["openapi", "playwright"],
  "test_count": 120,
  "passed": 118,
  "failed": 2,
  "failures": [
    {
      "test": "AC-2",
      "runner": "openapi",
      "error": "...",
      "fix": "..."
    },
    {
      "test": "login flow",
      "runner": "playwright",
      "error": "...",
      "fix": "..."
    }
  ],
  "contract_violations": [],
  "next_action": "交付 | 修复后重跑",
  "details": [<verdict1>, <verdict2>]
}
```

## OpenAPI Runner（内部桥接）

openapi runner 内部自动选择底层 adapter：
- 检测到 `pom.xml` → rest-assured（Java/SpringBoot）
- 检测到 `requirements.txt` / `pyproject.toml` → schemathesis（Python/FastAPI）
- 其他 → schemathesis（默认）

底层 adapter 保持独立 CLI 支持：
```bash
# 直接调用 schemathesis
python .claude/skills/contract-test/adapters/schemathesis_runner.py \
    --openapi openapi.yaml --base-url http://localhost:8080 --output /tmp/v.json

# 直接调用 rest-assured
python .claude/skills/contract-test/adapters/rest_assured_runner.py \
    --openapi openapi.yaml --base-url http://localhost:8080 --output /tmp/v.json
```

## Playwright Runner

前置：
- `npm install -D @playwright/test`
- `npx playwright install --with-deps`

自动行为：
- 查找 `playwright.config.{ts,js,mjs,cjs}`
- 查找最近 `package.json` 确定项目根目录
- 通过 `TEST_BASE_URL` 环境变量注入 base-url
- 解析 `npx playwright test` 输出，提取 passed/failed/skipped

## 质量门禁

- **任何 runner exit != 0** → 整体 FAIL
- **无 openapi.yaml** → 拒绝运行（fitness 规则）
- **被测服务不可达** → 明确报错，不返回假通过
- **runner 加载失败** → 降级报告 ERROR，不跳过

## 与 Evaluator Agent 的关系

```
evaluator → contract-test skill → runner → verdict.json → evaluator verdict
```

本 skill 只负责运行测试和产 verdict，评分和 verdict 格式化由 Evaluator agent 完成。

## 添加新 Runner

1. 新建 `runners/<name>_runner.py`，实现 `run(openapi, base_url, output) -> int`
2. 在 `run.py` 的 `RUNNER_MODULES` 字典登记：`"<runner-name>": "<name>_runner"`
3. 在 `detectors/project_type.py` 的 `get_recommended_runners()` 补充项目类型映射

## 关联

- Agent：`agents/evaluator.md`
- 模板：`templates/evaluator-rubric.md`

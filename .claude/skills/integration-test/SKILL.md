---
name: integration-test
description: 集成测试运行器，由 evaluator agent 调用。按技术栈选 adapter 跑契约测试，输出 verdict.json。触发关键词：integration test、集成测试、契约验收、schemathesis、e2e 测试。
model: sonnet
---

# Integration Test Skill

> evaluator agent 唯一的"测试执行器"。agent 负责打分判断（按 rubric），本 skill 负责实际跑测试。

## 边界（重要）

- ✅ **仅由 evaluator 调用**：generator 自测走单元测试，不走本 skill（保 GAN 三角独立性）
- ✅ **adapter 是内部实现**：本 skill 在 `scripts/adapters/` 下按 stack 路由，**不**调用其他 skill
- ✅ **只产出原始测试结果**：写 `INTEGRATION_TEST_REPORTS`；evaluator 自己写 `EVAL_VERDICTS`
- ❌ **不修改被测代码**
- ❌ **不读 generator 的 README / 自述**

## 输入输出

### 输入

```bash
python .claude/skills/integration-test/scripts/run.py \
  --story-id <id> \
  --case-id <case-id> \
  --contract <path/to/contract.md> \
  --project-root <被测项目根> \
  [--handoff <path/to/handoff-artifact.md>] \
  [--health-timeout 30] \
  [--dry-run]
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--story-id` / `--case-id` | 是 | verdict 文件路径与归档键 |
| `--contract` | 是 | contract.md（SSOT，由 doc-librarian 产出，包含接口契约定义） |
| `--project-root` | 否 | 被测项目根，默认 cwd（含 pom.xml/package.json/...） |
| `--handoff` | 否 | generator handoff-artifact.md，frontmatter `service` 段提供启动参数 |
| `--health-timeout` | 否 | 服务健康检查超时秒数，默认 30 |
| `--dry-run` | 否 | 仅打印探测结果与计划命令，不启动服务 |

### 输出

| 路径 | 内容 |
|------|------|
| `.chatlabs/reports/integration-tests/<story>/<case>.json` | 结构化 verdict（schema 见下文） |
| `.chatlabs/reports/integration-tests/<story>/<case>.log` | adapter 原始日志 |
| `.chatlabs/reports/integration-tests/<story>/<case>.service.log` | 被测服务 stdout/stderr |
| 退出码 | 0=PASS / 1=FAIL / 2=ERROR |

### Verdict Schema

```json
{
  "schema_version": "1.0",
  "ts": "2026-05-06T...",
  "story_id": "...", "case_id": "...",
  "stack": "spring-boot",
  "adapter": "http-schemathesis",
  "base_url": "http://localhost:8080",
  "verdict": "PASS|FAIL|ERROR",
  "totals": {"passed": 10, "failed": 2, "errors": 0},
  "failures": [
    {"endpoint": "...", "method": "GET", "reason": "...",
     "actual": "...", "expected": "...",
     "curl": "curl -X GET ...", "severity": "major"}
  ],
  "service": {"start_cmd": "...", "health_url": "...", "port": 8080,
              "started_at": "...", "stopped_at": "...", "pid": 12345,
              "source": "handoff|stack-default|explicit"},
  "raw_log": ".chatlabs/reports/integration-tests/<story>/<case>.log",
  "error_message": null
}
```

## 流程

```
1. stack_detect.py 探测项目技术栈（按 pom.xml / pyproject.toml / package.json 特征）
2. ServiceConfig 决议：
     handoff-artifact.md frontmatter service 段
       ↓ 缺失
     stack 默认表（spring-boot → mvn spring-boot:run / fastapi → uvicorn / node-http → npm run start）
       ↓ 都没有
     verdict=ERROR 退出
3. service_runner.py 启动服务，轮询 health_url 直到通过或超时
4. adapter.run() 跑测试（http-schemathesis 调 uvx schemathesis run）
5. verdict_writer.py 序列化 AdapterResult 为 JSON
6. try/finally 强杀服务（SIGTERM → 10s → SIGKILL）
```

## Stack 支持矩阵

| Stack | 探测特征 | Adapter | 默认启动命令 |
|-------|---------|---------|------------|
| spring-boot | pom.xml/build.gradle 含 `spring-boot-starter` | http-schemathesis | `mvn spring-boot:run` |
| fastapi | pyproject.toml/requirements.txt 含 `fastapi` | http-schemathesis | `uvicorn app.main:app --port 8000` |
| node-http | package.json deps 含 express/koa/nestjs/fastify/hapi | http-schemathesis | `npm run start` |
| web-frontend | package.json deps 含 react/vue/next/nuxt/svelte | **NOT_IMPLEMENTED** | — |
| unknown | 无可识别清单 | **ERROR** | — |

## 三方依赖

- **uvx**（必须）：`pip install uv` 或 `brew install uv`。schemathesis 通过 `uvx --quiet schemathesis run` 按需拉取并缓存
- **被测项目自身**：构建工具（mvn / uvicorn / npm）须可执行

## 与 evaluator 的边界

| 职责 | 归属 |
|------|------|
| 启动服务、跑测试、采集失败明细 | **本 skill** |
| 按 evaluator-rubric.md 打分（functionality / contract / quality / maintainability） | **evaluator agent** |
| 写 `EVAL_VERDICTS`（最终 verdict） | **evaluator agent** |
| 失败 ×3 阻断 + Blocker 上报 | **evaluator agent** |

## 失败约定

- `verdict=ERROR` 视为基础设施问题（uvx 缺失 / 服务起不来 / openapi 文件丢失），**不计入 evaluator retry 次数**
- `verdict=FAIL` 才是真正的契约违规，evaluator 计入 retry，超过 3 次写 Blocker

## 关联

- 主入口：`.claude/skills/integration-test/scripts/run.py`
- 路径常量：`.claude/scripts/paths.py` 中 `INTEGRATION_TEST_REPORTS`
- 调用方：`.claude/agents/evaluator.md`
- 服务声明合约：`.claude/agents/generator.md`（handoff-artifact.md 的 `service` 段）
- 评分规范：`.claude/templates/evaluator-rubric.md`

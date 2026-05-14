---
name: integration-test
description: 集成测试运行器，由 generator/evaluator agent 调用。按技术栈选 adapter 跑契约测试，输出 verdict.json。触发关键词：integration test、集成测试、契约验收、curl 测试、e2e 测试。
model: sonnet
---

# Integration Test Skill

> GAN 阶段的测试执行器。Generator 自验、Evaluator 复跑都走本 skill；
> evaluator 复跑结果是最终判定（generator 仅自验比对）。
> 评分机制已废弃 —— verdict 完全由实际测试通过/失败决定。

## 边界（重要）

- ✅ **两侧均可调用**：generator 跑 `--role=generator` 自验，evaluator 跑 `--role=evaluator` 复跑
- ✅ **最终判定以 evaluator 为准**：generator verdict 仅作差异参考
- ✅ **adapter 是内部实现**：本 skill 在 `scripts/adapters/` 下按 stack + yaml 存在性路由，**不**调用其他 skill
- ✅ **只产出原始测试结果**：写 `INTEGRATION_TEST_REPORTS`；evaluator 自己写 `EVAL_VERDICTS`
- ❌ **不修改被测代码**
- ❌ **不读 generator 的 README / 自述**（保 GAN 独立性）
- ❌ **不打分**（评分维度/rubric/total_score 已全部废弃）

## 输入输出

### 输入

```bash
python .claude/skills/integration-test/scripts/run.py \
  --story-id <id> \
  --case-id <case-id> \
  --contract <path/to/contract.md> \
  --project-root <被测项目根> \
  --role {generator|evaluator} \
  [--curl-tests <path/to/curl-tests.yaml>] \
  [--adapter http-curl|http-schemathesis|web-playwright] \
  [--handoff <path/to/handoff-artifact.md>] \
  [--health-timeout 30] \
  [--dry-run]
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--story-id` / `--case-id` | 是 | verdict 文件路径与归档键 |
| `--contract` | 是 | contract.md（doc-librarian 产出，含接口契约 SSOT） |
| `--role` | 否 | `generator`（自验）/ `evaluator`（最终判定）。默认 `evaluator` |
| `--curl-tests` | 否 | curl-tests.yaml 显式路径；缺省按约定 `STORE_DIR/<story>/cases/<case>.tests.yaml` |
| `--adapter` | 否 | 显式覆盖 adapter；缺省由 stack_detect + yaml 存在性决议 |
| `--project-root` | 否 | 被测项目根，默认 cwd |
| `--handoff` | 否 | generator handoff-artifact.md，frontmatter `service` 段提供启动参数 |
| `--health-timeout` | 否 | 服务健康检查超时秒数，默认 30 |
| `--dry-run` | 否 | 仅打印探测结果与计划命令，不启动服务 |

### 输出

| 路径 | 内容 |
|------|------|
| `.chatlabs/reports/integration-tests/<story>/<case>.<role>.json` | 结构化 verdict（schema 见下文） |
| `.chatlabs/reports/integration-tests/<story>/<case>.<role>.log` | adapter 原始日志 |
| `.chatlabs/reports/integration-tests/<story>/<case>.<role>.service.log` | 被测服务 stdout/stderr |
| 退出码 | 0=PASS / 1=FAIL / 2=ERROR |

### Verdict Schema（v2.0）

```json
{
  "schema_version": "2.0",
  "ts": "2026-05-13T...",
  "story_id": "...", "case_id": "...",
  "role": "evaluator",
  "stack": "spring-boot",
  "adapter": "http-curl",
  "base_url": "http://localhost:8080",
  "verdict": "PASS|FAIL|ERROR",
  "totals": {"passed": 10, "failed": 0, "errors": 0, "skipped": 0},
  "failures": [
    {"endpoint": "/api/v1/users", "method": "POST", "reason": "status mismatch: actual=500 expected=201",
     "actual": "HTTP 500 body={\"err\":\"...\"}", "expected": "HTTP 201",
     "curl": "curl -X POST 'http://localhost:8080/api/v1/users' -H ... -d ...",
     "severity": "major"}
  ],
  "service": {"start_cmd": "...", "health_url": "...", "port": 8080,
              "started_at": "...", "stopped_at": "...", "pid": 12345,
              "source": "handoff|stack-default|explicit"},
  "raw_log": ".chatlabs/reports/integration-tests/<story>/<case>.<role>.log",
  "error_message": null
}
```

> v1.0 的 `scores` / `total_score` / `next_action` 字段已删除。verdict 完全由 totals + failures 决定，不再叠加主观评分。

## curl 用例 yaml schema

planner 拆 case 时同步产出，路径 `.chatlabs/task/store/<story>/cases/<case_id>.tests.yaml`：

```yaml
case_id: STORY-123/CASE-01
base_url: ${BASE_URL}           # service_runner 注入实际 URL
defaults:                        # 可省略
  headers:
    Content-Type: application/json
tests:
  - name: AC-001-create-201
    ac: AC-001                  # 必填，关联 contract §5 AC-NNN
    request:
      method: POST
      path: /api/v1/users
      body: {name: alice}
    expect:
      status: 201               # 必填
      json:                      # 可选，每条独立断言
        $.id: {exists: true, type: string}   # 存在性 + 类型
        $.status: pending                     # 等值
    capture:                     # 抓响应字段进 context，下条用 ${user_id}
      user_id: $.id
  - name: AC-003-get-by-id
    ac: AC-003
    depends_on: AC-001-create-201   # 前置失败 → 本条 skipped 计入 errors
    request:
      method: GET
      path: /api/v1/users/${user_id}
    expect:
      status: 200
```

**断言能力刻意收窄**：
- 仅支持 `status`（整数）和 `json`（等值 / `{exists: bool}` / `{type: string|int|number|bool|list|dict}`）
- 禁止 jq 表达式、pre-request 脚本、条件分支
- 变量替换 `${VAR}` 同时解析 capture context 与环境变量（context 优先）
- 单 yaml 测试数 ≤ 8 条（超量拆 case）

完整模板见 `.claude/templates/story/curl-tests-template.yaml`。

## 流程

```
1. stack_detect.py 探测项目技术栈
2. adapter 决议：
     --adapter 显式指定 → 用
     stack 推荐 http-curl + yaml 存在 → http-curl
     stack 推荐 http-curl + yaml 不存在 → fallback http-schemathesis（stderr 警告）
3. ServiceConfig 决议：handoff > stack 默认 > ERROR
4. service_runner.py 启动服务，轮询 health_url
5. adapter.run() 跑测试，输出 AdapterResult
6. verdict_writer.py 序列化 → <case>.<role>.json
7. try/finally 强杀服务（SIGTERM → 10s → SIGKILL）
```

## Stack 支持矩阵

| Stack | 探测特征 | 默认 Adapter | Fallback | 默认启动命令 |
|-------|---------|------------|---------|------------|
| spring-boot | pom.xml/build.gradle 含 `spring-boot-starter` | http-curl | http-schemathesis | `mvn spring-boot:run` |
| fastapi | pyproject.toml/requirements.txt 含 `fastapi` | http-curl | http-schemathesis | `uvicorn app.main:app --port 8000` |
| node-http | package.json deps 含 express/koa/nestjs/fastify/hapi | http-curl | http-schemathesis | `npm run start` |
| web-frontend | package.json deps 含 react/vue/next/nuxt/svelte | web-playwright (stub) | — | — |
| unknown | 无可识别清单 | **ERROR** | — | — |

> **http-curl 是默认 adapter**：planner 必须为每个后端 case 产出 curl-tests.yaml。
> **http-schemathesis 仅作 fallback**：yaml 缺失时降级使用并打 stderr 警告，便于过渡。
> **web-playwright 本期 stub**：调用直接返回 `verdict=ERROR(not implemented)`，前端 E2E 在后续 PR 落地。

## 三方依赖

| Adapter | 依赖 | 安装 |
|---------|------|------|
| http-curl | `requests`, `pyyaml`, `jsonpath-ng` | `uv pip install requests pyyaml jsonpath-ng` |
| http-schemathesis | `uvx`（schemathesis 通过 uvx 按需拉取） | `pip install uv` 或 `brew install uv` |
| web-playwright | 后续实现时确定 | — |

## 失败约定

- `verdict=ERROR` 视为基础设施问题（依赖缺失 / 服务起不来 / yaml 缺失 / 解析失败），**不计入 evaluator retry**
- `verdict=FAIL` 才是契约违规，evaluator 计入 retry，超过 3 次写 Blocker
- 单条用例的连接异常→立即终止整轮（verdict=ERROR）；超时/断言失败→单条 FAIL 不短路

## 关联

- 主入口：`.claude/skills/integration-test/scripts/run.py`
- 路径常量：`.claude/scripts/paths.py` 中 `INTEGRATION_TEST_REPORTS` / `STORIES_DIR`
- 调用方：`.claude/agents/generator.md`（自验）、`.claude/agents/evaluator.md`（最终判定）
- 服务声明合约：`.claude/agents/generator.md`（handoff-artifact.md 的 `service` 段）
- 用例模板：`.claude/templates/story/curl-tests-template.yaml`

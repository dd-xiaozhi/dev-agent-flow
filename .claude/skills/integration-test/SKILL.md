---
name: integration-test
description: 统一集成测试入口。自动探测项目技术栈（Java/pom.xml、前端/package.json、Python/requirements.txt）并路由到对应测试 adapter 执行集成测试，输出统一 schema 的 verdict.json。
---

# 统一集成测试入口

> 自动识别项目技术栈 → 路由到对应适配器 skill → 输出统一 schema 的 verdict.json

## 核心流程（必须严格遵守）

### 1. 项目类型自动探测（第一步，必须先做）

在 `project_root` 下按优先级检测，**命中第一个即停止**：

| 优先级 | 检测文件 | 项目类型 | 调用的 adapter skill |
|-------|---------|---------|---------------------|
| 1（最高） | `pom.xml` | Java / Spring Boot | `/java-testing` |
| 2 | `package.json` | 前端（React/Vue/Angular/Node.js） | `/frontend-testing`（待实现） |
| 3 | `requirements.txt` / `pyproject.toml` | Python / FastAPI / Flask | `/python-testing`（待实现） |
| 4 | `*.http` / `postman_collection.json` | 纯 HTTP API 项目 | `/curl-testing`（待实现） |
| 5（最低） | 未匹配以上任何 | 未知类型 | 返回 `verdict=ERROR` + 说明"未找到对应技术栈适配器" |

**为什么有优先级？** 混合技术栈项目（如 Java + 前端 monorepo）中，后端测试通常更关键，优先走 Java 适配器。如需要特定类型，用户可显式传入 `force_stack` 参数覆盖。

### 2. 参数透传（原样传给 adapter）

```json
{
  "project_root": "<绝对路径>",
  "spec_path": "<spec.md 绝对路径>",
  "story_id": "<story id>"
}
```

可选覆盖参数：
- `force_stack: "java" | "frontend" | "python" | "curl"` — 强制指定技术栈，跳过自动探测

### 3. 调用对应 Adapter Skill

执行 `Skill(skill_name, args)`，**等待 skill 执行完成**。

> 重要：**不要自己写测试代码**，所有测试逻辑在 adapter skill 内执行。你只负责调度、等待结果、输出归一化。

### 4. 结果归一化（所有 adapter 必须遵守）

无论什么技术栈，输出格式完全统一。Adapter skill 的最终输出必须写入：

```
<project_root>/.chatlabs/reports/integration-tests/<story_id>/verdict.json
```

Schema（严格遵守，字段不可缺）：

```json
{
  "verdict": "PASS | FAIL | ERROR",
  "totals": {
    "tests": 10,
    "passed": 10,
    "failed": 0,
    "errors": 0,
    "skipped": 0
  },
  "ac_coverage": {
    "passed_acs": ["AC-001", "AC-002"],
    "failed_acs": []
  },
  "failures": [
    {
      "ac": "AC-003",
      "test_method": "should_return_401_When_TokenExpired",
      "reason": "AssertionError: expected status 401 but was 500",
      "stack_trace": "...",
      "severity": "major | critical | minor"
    }
  ],
  "meta": {
    "test_framework": "junit5 | jest | pytest | curl",
    "adapter_used": "java-testing",
    "test_file_path": "src/test/java/.../xxxIntegrationTest.java"
  }
}
```

**字段语义：**
- `verdict=PASS`：所有测试通过（totals.failed = 0 + totals.errors = 0）
- `verdict=FAIL`：至少一个测试失败（业务断言不通过）
- `verdict=ERROR`：环境问题、编译失败、依赖缺失、找不到对应 adapter 等基础设施问题

## 适配器注册机制

本 skill 同目录下 `adapters.json` 维护所有可用适配器：

```json
{
  "adapters": [
    {
      "name": "java-testing",
      "detect_files": ["pom.xml"],
      "skill_name": "/java-testing",
      "enabled": true
    },
    {
      "name": "frontend-testing",
      "detect_files": ["package.json"],
      "skill_name": "/frontend-testing",
      "enabled": false
    },
    {
      "name": "python-testing",
      "detect_files": ["requirements.txt", "pyproject.toml"],
      "skill_name": "/python-testing",
      "enabled": false
    },
    {
      "name": "curl-testing",
      "detect_files": ["*.http", "postman_collection.json"],
      "skill_name": "/curl-testing",
      "enabled": false
    }
  ]
}
```

**新增技术栈的正确姿势（开闭原则）：**
1. 新建 adapter skill（如 `/go-testing`），保证输出符合统一 verdict.json schema
2. 在 `adapters.json` 加一行注册
3. ✅ **完成！Evaluator 零修改直接可用**

## 执行纪律（MUST / MUST NOT）

✅ **必须**：先探测项目类型，再调用对应 adapter
✅ **必须**：等待 adapter skill 完整执行完成
✅ **必须**：最终输出 `verdict.json` 并放在规定路径
❌ **禁止**：直接在本 skill 内写测试代码
❌ **禁止**：绕过 adapter 直接跑 `mvn test` / `npm test`
❌ **禁止**：修改或增强 adapter 输出的 verdict 内容（只做透传）
❌ **禁止**：技术栈不匹配时猜测试方式，直接返回 `verdict=ERROR`

## 错误处理

| 场景 | verdict | meta.error_message |
|------|---------|-------------------|
| 未找到任何匹配的适配器 | `ERROR` | `"No adapter found for project type: unknown"` |
| 适配器 `enabled=false` | `ERROR` | `"Adapter 'xxx-testing' is disabled, please enable in adapters.json"` |
| 适配器执行异常（编译失败 / 依赖缺失） | `ERROR` | 直传底层错误信息 |
| 适配器未输出 verdict.json | `ERROR` | `"Adapter did not produce verdict.json at expected path"` |

## 参考

- 适配器规范：`adapters.json`
- 已实现适配器：`java-testing`
- 待实现：`frontend-testing` / `python-testing` / `curl-testing`

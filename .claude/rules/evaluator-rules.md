# Evaluator Fallback 硬规则

> 当被测项目无 `docs/knowledge/tech/backend/coding-style.md` + `fitness-rules.md` 时，Evaluator Phase 1 使用本文件作为内置规则白名单。

## 硬规则（命中即 FAIL）

| Rule ID | 描述 | severity |
|---------|------|----------|
| `no-hardcoded-path` | 代码中硬编码 `docs/...`、`/Users/...`、绝对项目路径 | major |
| `no-copy-paste` | 同一文件或跨文件出现 ≥ 10 行近似重复代码块，须抽工具方法 | major |
| `reuse-existing-utils` | 改动引入新方法时，若现有 utils 已有等价实现须复用 | major |
| `single-responsibility` | 单方法 > 80 行；超出须拆 | major |
| `no-dead-code` | 改动引入的 import / 变量 / 方法立即未被使用 | major |

> **触发 FAIL 的判定**：仅 `severity ∈ {critical, major}` 的 failure 计入。`minor` 仅作建议，写入 failures 数组但不阻断。

## 软建议（命中写 failures[] 但不阻断）

- 命名风格（驼峰 / 蛇形）与项目主流不一致
- 公开 API 缺 javadoc / docstring
- 单元测试缺断言消息
- log 级别明显不当（生产路径写 DEBUG / 调试 println）

> 这些写到 failures[]，但不引发 FAIL；Generator 可选择处理。

## Severity 分级

| severity | 含义 | 是否计入 FAIL |
|----------|------|--------------|
| `critical` | 严重违规（安全 / 数据正确性 / 核心契约违背） | 是 |
| `major` | 重要违规（命中硬规则白名单） | 是 |
| `minor` | 软建议（命名 / 注释 / 风格类） | 否（仅写 failures[]） |

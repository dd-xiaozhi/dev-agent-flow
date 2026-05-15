# 单元测试（团队约定）

JUnit 5 + Mockito + AssertJ 的 API 写法 AI 已熟，本文档只列项目约定。

## 团队规则

1. **不启动 Spring 容器**：用 `@ExtendWith(MockitoExtension.class)`，单元测试出现 `@SpringBootTest` 是 review 不通过项。
2. **所有外部依赖 Mock**：Repository、第三方 Client、其他 Service 一律 `@Mock`，单测只验证当前类逻辑。
3. **AAA 注释用中文标注**：`// 准备` / `// 执行` / `// 验证`——团队 review 约定，让结构一眼可读。
4. **命名公式**：`should_<期望>_When_<场景>`（与 SKILL.md 全局规范一致）。

## 命名示例（团队认可的几种场景）

| 场景 | 示例 |
|------|------|
| 正常路径 | `should_ReturnUser_When_ValidId` |
| 异常路径 | `should_ThrowException_When_UserNotFound` |
| 边界 | `should_ReturnEmptyList_When_NoMatches` |
| 重试 | `should_Retry_When_TokenExpired` |
| 降级 | `should_Fallback_When_RetriesExhausted` |

## 验证调用次数的约定

`verify(client, times(N))` 只在**次数有业务语义**时用——重试、降级、批量分页。不要对每个调用都 verify，那是 noise。

## 反模式（项目内常见的错误）

- ❌ 单元测试里用 `@SpringBootTest` / `@Autowired`：套件慢一个数量级
- ❌ 一个测试方法测多个分支：失败时定位困难，拆开
- ❌ Mock 了 `findById` 但忘记 `Optional.of(...)` 包装：返回 null 后 NPE，排查很久才发现

> 测异常时优先 `assertThatThrownBy(...)` 链式断言（AssertJ 风格），不要 try-catch。

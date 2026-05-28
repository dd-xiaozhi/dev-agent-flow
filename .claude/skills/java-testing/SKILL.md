---
name: java-testing
description: 为 Java / Spring Boot 项目编写符合团队规范的测试——覆盖单元/集成测试、AOP Mock 第三方异常、错误码契约（@ExceptionHandler）与 X-Simulate-Failure 故障注入 Header 协作。TRIGGER：写/补/改测试，Mock 第三方异常（Token 过期/限流/超时），定义错误码，编辑 *Test.java。SKIP：性能压测、覆盖率配置、只问 JUnit API 用法。
---

# Java 测试规范化指南

> 本指南不教 JUnit / Mockito / AssertJ / MockMvc / WireMock 的基础 API，只约定**团队规范、决策路径、踩过的坑**。

## 三条不可妥协的红线

1. **业务代码绝不写测试逻辑**。任何 `if (env == "test")` / `if (header == "mock")` 写在 Service / Controller 里都是错的——用 AOP 切面 + `@Profile("test")` 隔离，详见 [aop-mock-pattern.md](references/aop-mock-pattern.md)。
2. **异常处理器必须显式设 Content-Type**。`@RestControllerAdvice` 返回错误体前先 `.contentType(MediaType.APPLICATION_JSON)`——尤其当接口 `produces = "application/pdf"` 时（曾发生过 `HttpMessageNotWritableException` 事故，见 [troubleshooting.md](references/troubleshooting.md)）。
3. **REST 接口的错误响应永远是结构化 JSON**。统一格式 `{ code, message, timestamp, path, traceId }`，前端 / QA 按 `code` 字段断言，**永远不**依赖 message 文案。GraphQL / gRPC / SSE 不在此规则内。

## 测试分层与命名

| 类型 | 命名 | 工具 | 阶段 |
|------|------|------|------|
| 单元 | `*Test.java` | JUnit5 + Mockito + AssertJ | `mvn test`（Surefire） |
| 集成 | `*IntegrationTest.java` | `@SpringBootTest` + MockMvc + WireMock | `mvn verify`（Failsafe） |

**两个必须做的项目配置**：
- 测试包路径**镜像** main（`src/main/.../UserService.java` ↔ `src/test/.../UserServiceTest.java`）
- pom.xml 给 Failsafe 显式配 `<include>**/*IntegrationTest.java</include>`，给 Surefire 配同款 `<exclude>`，避免一份测试跑两遍

命名公式：**`should_<期望>_When_<场景>`**（全项目统一一种，不混用 BDD / DisplayName 风格）。

## 决策树：写哪种测试

```
要测的对象是？
├─ 单一类纯逻辑（无 IO、无 Spring 依赖）       → 单元测试 + Mock 依赖
├─ Controller 请求/响应/校验/序列化/错误码    → 集成测试 + MockMvc
├─ 认证 / 授权 / 角色权限                     → 集成测试 + @WithMockUser
├─ Repository / JPA 查询                       → 集成测试 + Testcontainers
├─ 调第三方 HTTP（重试 / 降级）               → 集成测试 + WireMock
├─ 上游 schema 漂移防护（关键业务接口）        → 契约测试（Pact）
├─ QA 在测试环境复现第三方故障               → AOP 切面 Mock
├─ @Async / @Scheduled / Kafka 异步任务      → 集成测试 + Awaitility，不要 @Transactional
└─ 跨 Service 复杂编排                         → 先拆 Service 单元测，再 1-2 个集成测试验证编排
```

## FIRST 原则

**F**ast / **I**solated / **R**epeatable / **S**elf-validating / **T**imely——任何违反项都是技术债。

关键工程纪律：
- 注入 `Clock` 而非用 `LocalDateTime.now()`，否则测试不可重复
- Testcontainers 镜像必须 pin 到 patch 版本（`postgres:15.3`，**禁止** `:15` 或 `:latest`）
- 使用 Singleton Container 模式跨测试共享

## 团队项目约定（AI 不知道的部分）

### 错误码字典（项目契约）

| HTTP | code | 说明 |
|------|------|------|
| 401 | `TOKEN_EXPIRED` / `TOKEN_INVALID` / `UNAUTHENTICATED` | 认证类 |
| 403 | `FORBIDDEN` | 已认证但权限不足 |
| 404 | `RESOURCE_NOT_FOUND`（可细化如 `PDF_NOT_FOUND`） | 资源不存在 |
| 429 | `RATE_LIMITED` | 限流 |
| 502 | `THIRD_PARTY_ERROR` | 上游业务异常 |
| 503 | `SERVICE_UNAVAILABLE` | 上游不可用（重试耗尽走这个） |
| 500 | `INTERNAL_ERROR` | 兜底，必须告警 |

### QA 故障注入 Header（团队特色）

第三方异常通过 `X-Simulate-Failure: <type>` 触发，**仅在 `spring.profiles.active=test` 时生效**：

| 值 | 触发 | 期望响应 |
|----|------|---------|
| `token_expired` | TokenExpiredException | 401 / `TOKEN_EXPIRED` |
| `timeout` | SocketTimeoutException | 调用方超时 / 503 |
| `server_error` | ServiceUnavailableException | 503 / `SERVICE_UNAVAILABLE` |
| `rate_limit` | RateLimitExceededException | 429 / `RATE_LIMITED` |

实现方案见 [aop-mock-pattern.md](references/aop-mock-pattern.md)，QA 协作 SOP 见 [qa-collaboration.md](references/qa-collaboration.md)。

### 集成测试断言三件套（团队约定）

异常响应必须断言这三项，不能只看 status：

```
status() + header().contentType(APPLICATION_JSON) + jsonPath("$.code").value("...")
```

## Gotchas（团队踩过的具体坑）

1. 业务代码绝不写 `if (env == "test")` —— 用 AOP + `@Profile("test")` 隔离(详见 [aop-mock-pattern.md](references/aop-mock-pattern.md))
2. `@RestControllerAdvice` 错误响应必须显式 `.contentType(APPLICATION_JSON)`(曾因 PDF 接口踩 `HttpMessageNotWritableException`)
3. Boot 3.4+:`@MockBean` → `@MockitoBean`(容易漏改,编译不报错运行时 NPE)
4. Testcontainers 镜像必须 pin patch 版本(`postgres:15.3`),禁 `:15` 或 `:latest`(否则 CI 不可重复)
5. 异步测试不要加 `@Transactional`(事务边界与 `@Async` 冲突,异步任务看不到主线程的 DB 数据)
6. 断异常响应必须三件套:`status + Content-Type + jsonPath("$.code")`,只断 status 漏掉契约破坏
7. `LocalDateTime.now()` 让测试不可重复 —— 注入 `Clock` 并 mock 时间

## references 索引

| 你正在做… | 读这个 |
|----------|-------|
| 写单元测试（命名约定、AAA 注释风格） | [unit-testing.md](references/unit-testing.md) |
| 写集成测试（断言三件套、Testcontainers 工程经验） | [integration-testing.md](references/integration-testing.md) |
| 写涉及登录态 / 角色 / JWT / CSRF 的测试 | [security-testing.md](references/security-testing.md) |
| 选 WireMock 还是 Pact | [contract-testing.md](references/contract-testing.md) |
| 准备测试数据（隔离策略取舍） | [test-data-management.md](references/test-data-management.md) |
| 异步 / 调度 / 事务边界 | [async-testing.md](references/async-testing.md) |
| QA 复现第三方故障（项目特色方案） | [aop-mock-pattern.md](references/aop-mock-pattern.md) |
| 异常响应格式 / 错误码 / 日志原则 | [error-handling.md](references/error-handling.md) |
| 提测交付物清单、协作 SOP | [qa-collaboration.md](references/qa-collaboration.md) |
| 团队踩过的具体坑 | [troubleshooting.md](references/troubleshooting.md) |

## 适用版本

Spring Boot 3.2+ · JUnit 5.10+ · Mockito 5.x · WireMock 3.x · AssertJ 3.x

**版本陷阱**：
- Boot 3.4+：`@MockBean` → `@MockitoBean`
- Boot 3.1+：Testcontainers 用 `@ServiceConnection` 替代 `@DynamicPropertySource`
- Boot 3.0+：`javax.*` → `jakarta.*`
- 老项目（Boot 2.x / JUnit 4）：先告知用户、再调整示例语法

## 扩展工具（按需引入）

`JaCoCo` 覆盖率 · `PIT` 突变测试 · `ArchUnit` 架构规则 · `Toxiproxy` 网络故障注入 · `Gatling` 性能基线。

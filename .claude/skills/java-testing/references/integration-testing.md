# 集成测试（团队约定 + 工程经验）

MockMvc / WireMock / Testcontainers 的 API 写法 AI 已熟，本文档只列项目约定和踩过的工程坑。

## 团队规则

1. **数据库用真实的，第三方用 Mock**：业务库走 Testcontainers / `@DataJpaTest`，对外 HTTP 走 WireMock。
2. **不允许 `@MockitoBean` 替换业务 Service**：那不是集成测试，是带容器的单元测试，慢且无意义。
3. **断言三件套必须齐**（异常路径强制）：
   ```
   status() + header().contentType(APPLICATION_JSON) + jsonPath("$.code")
   ```
   只断言 status 一律 review 打回——文案会改、code 是契约。
4. **路径变量用占位符**：`get("/api/{id}", id)` 而非字符串拼接（防注入 + 可读）。

## Testcontainers 三条工程纪律

这些是项目踩过坑得出的实战规则，AI 不会主动遵守：

1. **镜像版本 pin 到 patch**
   ```java
   new PostgreSQLContainer<>("postgres:15.3")   // ✅
   new PostgreSQLContainer<>("postgres:15")     // ⚠️ Docker tag 会漂移
   new PostgreSQLContainer<>("postgres:latest") // ❌ 今天通过明天 CI 挂
   ```

2. **Singleton Container 模式**：每个测试类一个 container 会让套件慢 N 倍。继承一个 `IntegrationTestBase` 让 container 全 JVM 共享，JVM 退出时统一关。

3. **本地开发开启 `testcontainers.reuse.enable=true`**（CI **不要**开，残留容器会污染下一次构建）。

## 配置写法（版本相关）

- **Boot 3.1+**：用 `@ServiceConnection`（自动绑定 DataSource 属性，比 `@DynamicPropertySource` 少 6 行模板）
- **Boot 3.0 及以下**：用 `@DynamicPropertySource` 手动 register

## 测试数据隔离的取舍

| 策略 | 适用 | 失效场景 |
|------|------|---------|
| `@Transactional` 回滚 | 同线程同步逻辑 | **异步任务测试不要用**——子线程拿不到主线程未提交数据，详见 [async-testing.md](async-testing.md) |
| `@BeforeEach` 手动 truncate | 异步 / 并发 / 跨连接 | 略慢，但稳 |
| 每测试随机租户前缀 | 大套件 + Singleton Container | 需要业务模型支持租户隔离 |

## WireMock 反模式

- ❌ 测试间共享 stub 不 reset：场景串扰是调试地狱。`@BeforeEach` 里 `wireMock.resetAll()` 是默认动作
- ❌ 测试直连真实第三方：CI 不稳 + 配额烧光
- ❌ WireMock 用固定端口 8089：并行测试冲突。用 `.options(wireMockConfig().dynamicPort())`

## 切片测试用不用？

默认用 `@SpringBootTest`——切片（`@WebMvcTest` / `@DataJpaTest`）能加速，但容易遗漏配置类引发的问题。除非测试 >100 个需要优化启动时间，否则不折腾。

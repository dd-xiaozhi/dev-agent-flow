# 团队踩过的具体坑

通用排查（Mock 不生效、Bean 找不到）AI 已会，本文档只记**团队真实遇到过、解决方式有特异性**的问题。

## HttpMessageNotWritableException（红线级，发生过事故）

**症状**：

```
HttpMessageNotWritableException:
No converter for [class java.util.LinkedHashMap]
with preset Content-Type 'application/pdf'
```

**根因**：接口 `produces = "application/pdf"` 正常返回 PDF；异常分支返回 JSON 错误体，但 Spring 沿用了 PDF 的 Content-Type，找不到 Map → PDF 的转换器。

**修法**（按优先级）：

1. **首选**：`@RestControllerAdvice` 异常处理器里显式 `.contentType(MediaType.APPLICATION_JSON)`
2. Controller 不写死 `produces`，让 Spring 协商
3. Filter 层强制覆盖 `response.setContentType("application/json")`

详见 [error-handling.md#关键陷阱](error-handling.md)。

## IDE 通过、CI 失败

排查顺序（按团队历史发生频率）：

1. **时区差异**：IDE 本地 zh_CN，CI UTC + en_US → application-test.yml 显式设 `spring.jackson.time-zone: Asia/Shanghai`
2. **端口冲突**：用了 `webEnvironment = DEFINED_PORT` → 改 `RANDOM_PORT`
3. **共享状态**：测试间通过静态字段 / 缓存隐式耦合 → 根治办法是测试互不依赖，`@DirtiesContext` 只是兜底
4. **隐式网络调用**：某些 starter 启动时 ping 外部服务 → application-test.yml 关掉对应自动配置

## `@Transactional` + `@Async` 失效

异步任务相关测试**禁用** `@Transactional`，详见 [async-testing.md](async-testing.md)。

## 动态值（timestamp / traceId）断言

`jsonPath("$.timestamp").exists()` 即可，**不要**断言具体值。需要稳定时间断言时注入 `Clock`。

## 测试套件变慢的排查顺序

1. 单元测试被误写成集成测试（带 `@SpringBootTest`）→ 拆出去
2. `@DirtiesContext` 滥用 → 每次重启容器，移除并确保测试不污染状态
3. Testcontainers 没开 reuse（仅本地）→ `~/.testcontainers.properties` 设 `testcontainers.reuse.enable=true`
4. Singleton Container 模式没用 → 见 [integration-testing.md](integration-testing.md)

## 版本兼容性提醒

- `@MockitoBean` / `@MockitoSpyBean`（包名 `org.springframework.test.context.bean.override.mockito`）从 **Boot 3.4 / Framework 6.2** 起为推荐写法
- Boot 3.3 及以下继续用 `@MockBean`，新代码升级 Boot 后再迁移

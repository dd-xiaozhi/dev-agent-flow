# AOP 切面模拟第三方异常（团队特色方案）

## 解决的痛点

你的服务作为中间层调用第三方（支付、PDF、AI 模型、银行接口...）。QA 在测试环境需要复现：
- Token 过期
- 上游超时
- 上游 5xx
- 限流（429）

但 QA 没法控制第三方接口，开发也不想在业务代码里写 `if (testMode)` 这种污染代码。

## 思路

**通过 AOP 切面 + 注解 + Header 触发，在测试环境拦截被标记的方法，按 Header 抛出对应异常**。业务方法本身不感知测试逻辑。

```
QA curl + X-Simulate-Failure: token_expired
       ↓
Filter / Interceptor 把 Header 放到 ThreadLocal 或 Request 上下文
       ↓
Controller → Service.method() (带 @Mockable 注解)
       ↓
AOP 切面拦截 → 读 Header → 抛 TokenExpiredException
       ↓
@RestControllerAdvice → 返回 401 + { code: TOKEN_EXPIRED, ... }
```

## 1. 定义注解

```java
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface Mockable {
    /** 注解可选 value，描述该方法可模拟哪些故障类型，便于文档化 */
    String[] supports() default {};
}
```

## 2. 实现切面

```java
@Slf4j
@Aspect
@Component
@Profile("test")  // 生产环境不加载，零侵入
public class ThirdPartyMockAspect {

    @Around("@annotation(com.example.annotation.Mockable)")
    public Object simulateFailure(ProceedingJoinPoint joinPoint) throws Throwable {
        HttpServletRequest request = currentRequest();
        if (request == null) {
            return joinPoint.proceed();  // 非 HTTP 上下文，正常执行
        }

        String simulate = request.getHeader("X-Simulate-Failure");
        if (simulate == null || simulate.isBlank()) {
            return joinPoint.proceed();
        }

        log.warn("[测试模式] 拦截 {}#{}，模拟故障: {}",
                joinPoint.getSignature().getDeclaringTypeName(),
                joinPoint.getSignature().getName(),
                simulate);

        switch (simulate) {
            case "token_expired":
                throw new TokenExpiredException("[mock] token 已过期");
            case "timeout":
                // 直接抛"读超时"异常，模拟上游慢导致的 SocketTimeout
                // 注意：不要 sleep 后再 throw —— sleep 期间上游 client 早已自行超时，
                //      throw 永远到不了客户端；如需触发真实超时链路，见下方"timeout 模式 B"
                throw new SocketTimeoutException("[mock] 上游读超时");
            case "server_error":
                throw new ServiceUnavailableException("[mock] 上游 503");
            case "rate_limit":
                throw new RateLimitExceededException("[mock] 上游限流");
            default:
                log.warn("未知 simulate 类型: {}，按正常逻辑执行", simulate);
                return joinPoint.proceed();
        }
    }

    private HttpServletRequest currentRequest() {
        RequestAttributes attrs = RequestContextHolder.getRequestAttributes();
        return (attrs instanceof ServletRequestAttributes sra) ? sra.getRequest() : null;
    }
}
```

**为什么 `@Profile("test")` 是关键**：Spring 在生产环境根本不会装配这个 Bean，即使生产请求带了 `X-Simulate-Failure` Header 也不会触发——这是安全底线。

### timeout 的两种模式

模拟"超时"有两种语义，选其一：

**模式 A：直接抛 SocketTimeoutException**（上面采用的写法）
- 优点：快、确定、与异常处理器解耦验证一致
- 用途：验证业务层对"读超时"异常的捕获、降级、重试逻辑

**模式 B：真实阻塞，让上游 Client 自身超时**
- 优点：触发完整的网络栈超时链路（连接超时 / 读取超时 / 整体超时）
- 写法：将 case 改为 `Thread.sleep(durationMs); return joinPoint.proceed();`，其中 `durationMs` 需 > Client 的 readTimeout
- 注意：测试阻塞会拖慢测试套件，仅在专门验证超时配置时使用

**绝不要写**：`Thread.sleep(N); throw new SocketTimeoutException(...)`——sleep 期间外层 client 早已超时返回，throw 永远到达不了客户端。

## 3. 标记业务方法

```java
@Service
public class PdfService {

    @Mockable(supports = {"token_expired", "timeout", "server_error", "rate_limit"})
    public byte[] generatePdf(String id) {
        // 纯业务逻辑，0 测试相关代码
        String token = thirdPartyAuthService.getToken();
        return thirdPartyPdfClient.download(id, token);
    }
}
```

`supports` 数组本身没有运行时作用，但**作为文档**告诉读者"这个方法支持哪些 mock 类型"——也方便后续自动生成 QA 测试文档。

## 4. Profile 配置

```yaml
# application-test.yml
spring:
  profiles:
    active: test
```

```yaml
# application-prod.yml
spring:
  profiles:
    active: prod
```

## 5. 给 QA 的使用示例

```bash
# 模拟 token 过期 → 期望 401 + code=TOKEN_EXPIRED
curl -i -X GET "http://test-api/afs/estimate/pdf/abc" \
  -H "X-Simulate-Failure: token_expired"

# 模拟超时 → 期望客户端超时 / 重试机制启动
curl -i -X GET "http://test-api/afs/estimate/pdf/abc" \
  -H "X-Simulate-Failure: timeout"

# 模拟上游 503 → 期望 503 + code=SERVICE_UNAVAILABLE
curl -i -X GET "http://test-api/afs/estimate/pdf/abc" \
  -H "X-Simulate-Failure: server_error"

# 模拟限流 → 期望 429 + code=RATE_LIMITED
curl -i -X GET "http://test-api/afs/estimate/pdf/abc" \
  -H "X-Simulate-Failure: rate_limit"
```

## 安全保证（三层）

1. **编译期**：`@Mockable` 注解只描述意图，不写任何条件分支
2. **装配期**：`@Profile("test")` 让切面在生产环境不进入 Bean 容器
3. **运行期**：切面只读 Request Header，不接受其他触发方式

即使代码被合并到主分支，生产环境也无法触发——可以放心上线。

## 集成测试如何验证 AOP 生效

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
@AutoConfigureMockMvc
class MockAspectIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void should_Return401_When_HeaderSimulatesTokenExpired() throws Exception {
        mockMvc.perform(get("/afs/estimate/pdf/{id}", "any-id")
                .header("X-Simulate-Failure", "token_expired"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("TOKEN_EXPIRED"));
    }

    @Test
    void should_Return503_When_HeaderSimulatesServerError() throws Exception {
        mockMvc.perform(get("/afs/estimate/pdf/{id}", "any-id")
                .header("X-Simulate-Failure", "server_error"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.code").value("SERVICE_UNAVAILABLE"));
    }
}
```

## 扩展模板

如果需要支持更多类型（如 `partial_response`、`malformed_json`），切面只需要加 case，业务方法的 `@Mockable(supports = ...)` 同步更新，QA 文档自动可生成。**不要为每种类型都建一个独立切面**——一个切面 + switch 已经足够清晰。

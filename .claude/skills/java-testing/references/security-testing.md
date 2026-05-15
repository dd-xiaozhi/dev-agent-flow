# Spring Security 测试（团队约定）

Spring Security Test 的 API（`@WithMockUser` / `@WithSecurityContext` / `SecurityMockMvcRequestPostProcessors`）AI 已熟，本文档只列项目约定和踩坑。

依赖必须显式引入：`spring-security-test`（`<scope>test</scope>`）。

## 团队规则

1. **角色断言用 `code` 而非 status 文案**：与 [error-handling.md](error-handling.md) 错误码字典对齐。
2. **POST/PUT/DELETE 测试默认带 CSRF**——除非项目的 `SecurityFilterChain` 显式 `.csrf(disable)`（无状态 REST + JWT 通常 disable，要确认）。
3. **方法级安全测试必须从容器拿 Bean**（`@PreAuthorize` 走代理才生效，直接 `new` 出来的对象不会触发）。

## 认证/授权错误码契约

| HTTP | code | 触发 |
|------|------|------|
| 401 | `UNAUTHENTICATED` | 未带凭证 / 凭证缺失 |
| 401 | `TOKEN_EXPIRED` | JWT 过期（细分场景） |
| 401 | `TOKEN_INVALID` | JWT 签名错 / 格式错 |
| 403 | `FORBIDDEN` | 已认证但权限不足 |

**重要**：Spring Security 默认的 `AccessDeniedHandler` / `AuthenticationEntryPoint` 返回**空 body + WWW-Authenticate**——必须自定义实现，让认证/授权失败也走项目统一错误 JSON，否则前端拿不到 `code` 字段。

## 注解选用速查

- 角色固定：`@WithMockUser(roles = {"ADMIN"})`——注意会自动加 `ROLE_` 前缀
- 直接用权限串（不带前缀）：`@WithMockUser(authorities = {"order:write"})`
- 依赖真实 user 属性（租户、订阅等级）：`@WithUserDetails(value = "...", userDetailsServiceBeanName = "...")`
- 自定义 JWT：写 `@WithSecurityContextFactory<MyAnnotation>` 构造 `JwtAuthenticationToken`

## 反模式（项目内常见错误）

- ❌ `@WebMvcTest` 切片测试缺 `spring-security-test`：过滤器链未装配，结果误导（要么全 401 要么全通过）
- ❌ 测试方法里手动 `SecurityContextHolder.setAuthentication(...)`：MockMvc 看不到，等于没设。**只用注解或 `RequestPostProcessor`**
- ❌ POST 不带 `.with(csrf())` 又怪业务返回 403：先排除 CSRF 再查授权
- ❌ 测试库塞生产用户的密码 hash：用 `@WithMockUser` 或 `{noop}plain` PasswordEncoder（仅 test profile）

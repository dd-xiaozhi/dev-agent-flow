# 与 QA 协作的测试规范

## 提测时交付给 QA 的"四件套"

| 文档 | 内容 | 形式 |
|------|------|------|
| 1. 接口契约 | 路径、方法、参数、响应 schema | Swagger / OpenAPI / contract.md |
| 2. 错误码表 | 当前接口可能返回的所有 code、HTTP 状态、含义 | 表格 |
| 3. 故障模拟 Header | 支持哪些 `X-Simulate-Failure` 类型、对应错误码 | 表格 + curl 示例 |
| 4. 测试数据准备 | 提测库的初始数据来源 / 准备脚本 / 清理方式 | README / sql 文件 |

缺一不可。少一项，QA 都会回来问，徒增沟通成本。

## 测试 Header 模板（贴在提测邮件 / 文档）

```markdown
### 测试 Header：X-Simulate-Failure

仅在 test profile 下生效，用于模拟上游故障：

| 值 | 触发效果 | 期望响应 |
|----|---------|---------|
| `token_expired` | 抛 TokenExpiredException | 401 + code=TOKEN_EXPIRED |
| `timeout` | 阻塞 10s 后抛 SocketTimeoutException | 调用方超时 / 503 |
| `server_error` | 抛 ServiceUnavailableException | 503 + code=SERVICE_UNAVAILABLE |
| `rate_limit` | 抛 RateLimitExceededException | 429 + code=RATE_LIMITED |

curl 示例：
\`\`\`bash
curl -i -X GET "https://test-api.example.com/afs/estimate/pdf/abc" \
  -H "X-Simulate-Failure: token_expired"
\`\`\`
```

## 协作流程（标准提测）

```
1. 开发完成自测（单元 + 集成 + AOP-Mock 触发跑通）
2. 提交测试文档（四件套）+ 接入测试环境
3. QA 用故障 Header 跑异常路径 + 正常用例
4. 缺陷反馈 → 开发修复 → 回归
```

**自测清单**：

- [ ] 所有 Controller 都有 `*IntegrationTest`，至少 1 个正常 + 1 个异常用例
- [ ] 所有调用第三方的 Service 都有 `@Mockable` 注解或对应 WireMock 测试
- [ ] 错误响应字段齐全（code / message / timestamp / path / traceId）
- [ ] 异常响应 Content-Type 是 `application/json`（即使接口正常返回 PDF/二进制）
- [ ] 提供给 QA 的 curl 示例都验证过

## 常见协作摩擦点 & 解法

| 摩擦 | 解法 |
|------|------|
| QA 无法复现"上游超时" | 用 AOP Mock 切面 + `X-Simulate-Failure: timeout` |
| 测试环境数据被互相污染 | 提供 init / cleanup 脚本，QA 每轮跑前清表 |
| 文案变更让自动化用例全挂 | 让 QA 用 jsonPath `$.code` 断言而非 `$.message` |
| 第三方测试账号配额烧光 | 测试环境用 WireMock 代理上游，不打真实接口 |
| QA 抓到 `HttpMessageNotWritableException` | 见 [troubleshooting.md](troubleshooting.md#http-message-not-writable) |

## 文档自动化建议

`@Mockable(supports = {...})` 数组是可读的——可以写一个简单的 Maven 插件 / 单元测试，扫描所有标记方法，自动生成"测试 Header 支持矩阵"文档。这样开发新加 case 不需要手动同步 QA 文档。

```java
@Test
void generateMockSupportMatrix() {
    // 用 reflections / spring component scan 扫所有 @Mockable
    // 输出到 docs/qa-mock-support.md
}
```

这是建议、不是强制——团队人少的时候手维护也行，超过 5 个接口就值得自动化。

# 测试数据管理（取舍指引）

Builder / ObjectMother / `@Sql` / Flyway 的实现 AI 已熟。本文档只列项目取舍。

## 三种数据来源各管什么

| 来源 | 用途 | 工具 |
|------|------|------|
| 代码构造（Builder / ObjectMother） | 单元测试、Service 集成测试 | 项目自建 |
| 声明式 SQL | Repository 集成测试、特定数据场景 | `@Sql`（支持 `@SqlMergeMode` 合并类级+方法级） |
| 迁移脚本 baseline | 全局基础数据（字典、配置） | Flyway / Liquibase |

混用很常见：Flyway 建表 → `@Sql` 插业务数据 → Builder 在测试方法里造对象。

## Flyway 关键原则

**测试用生产同款迁移脚本**（`spring.flyway.locations=classpath:db/migration`），不要为测试维护单独建表 SQL。否则方言差异、字段顺序、约束细节会让测试与生产漂移。

测试专用种子数据（mock 用户、测试租户）放 `src/test/resources/sql/` 用 `@Sql` 注入，**不要污染生产迁移**。

## 数据隔离 3 选 1（取舍）

| 策略 | 适用 | 失效场景 |
|------|------|---------|
| `@Transactional` 自动回滚 | 同线程同步逻辑 | 异步任务、跨连接事务、需要触发 DB trigger 时 |
| `@BeforeEach` 显式 truncate | 异步 / 并发 / 跨连接 | 略慢，但稳，需挑表清不能 truncate 字典表 |
| 每测试随机租户前缀 | Singleton Container 大套件 | 业务模型必须有租户字段 |

**推荐组合**：Singleton Container + Builder 默认用随机前缀 + 关键场景用 `@Sql` 准备。**避免**全套件依赖 `@Transactional`——一旦加 `@Async` 测试就要拆掉。

## Builder 默认值的两条铁律

1. **默认值必须是"业务上有效的对象"**——全 null 会让稍有遗漏的测试 NPE
2. **加字段时只改 Builder 默认值**——所有测试不需要改

## 时钟 / UUID：可重复性根基

业务代码注入 `Clock` 而非用 `LocalDateTime.now()`；UUID 同理（注入 `Supplier<UUID>`）。测试 `@TestConfiguration` 替换为固定值。这是 FIRST 中 **R**（Repeatable）的最常被忽视的违反点。

## 反模式（项目内常见错误）

- ❌ `new User(); setAll(...)` 在每个测试反复造 30 行：用 Builder
- ❌ 测试数据初始化写到 Flyway 迁移里：污染生产
- ❌ 用 `@DirtiesContext` 来"清状态"：每个测试重启容器，套件慢 10×，从根上查为什么需要 dirties
- ❌ 一份 `data.sql` 全局加载：随着测试增加变成几千行祖传文件，谁都不敢动

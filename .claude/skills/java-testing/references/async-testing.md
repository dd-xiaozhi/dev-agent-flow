# 异步 / 调度 / 事务测试（关键坑）

Awaitility / `@Async` / `CompletableFuture` / `StepVerifier` 的 API 写法 AI 已熟。本文档只列项目踩坑。

## 核心原则

异步状态变更**永远用 Awaitility 轮询断言**，**永远不**用 `Thread.sleep(N)` + 直接断言——前者快、稳；后者阈值难选 + CI 慢时假阴性。

## `@Transactional` 与异步的硬冲突

测试方法上 `@Transactional` 会自动回滚——同步逻辑下保证隔离，**但碰到异步会失效**：

| 场景 | `@Transactional` 测试方法是否可用 |
|------|--------------------------------|
| 同线程同步逻辑 | ✅ |
| `@Async` 任务 | ❌ 子线程拿不到主线程未提交事务的数据 |
| `@Scheduled` 任务 | ❌ 同上 |
| 嵌套 `TransactionTemplate.execute` | ⚠️ 数据可见性混乱 |
| 测 DB trigger 触发后的副作用 | ❌ 数据还在内存事务里 |

**规则**：异步 / 调度 / 跨连接相关测试**禁用** `@Transactional`，改用 `@BeforeEach` truncate + Awaitility 等待。

## Awaitility 调优经验

- `atMost`：业务期望耗时的 **2-3 倍**。CI 慢就放宽到 10s。**不要**写 60s——挂掉时要等 1 分钟才报错。
- `pollInterval`：100-200ms。过快烧 CPU，过慢误差大。
- **必须用 `untilAsserted(() -> assertThat(...))`**——失败信息完整。`.until(boolean)` 失败只报 `ConditionTimeoutException`，调试痛苦。

## 调度任务怎么测

- 测**业务逻辑**：直接调方法，不等 cron 触发。
- 测**调度本身被触发**：极少需要，通常不必怀疑 Spring 调度框架。如必须，properties 改 cron 为秒级 + `verify(job, atLeast(N))`。

## `TestTransaction`：少数场景的程序化提交

测"提交后 trigger / Listener / `@EventListener(phase=AFTER_COMMIT)` 才生效"时，用 `TestTransaction.flagForCommit()` + `TestTransaction.end()` 显式提交，再起新事务做断言。包路径 `org.springframework.test.context.transaction`。

## `@Async` 代理失效坑

同类内部方法调用不走 AOP 代理，`@Async` 失效：

```java
public void publicMethod() {
    this.asyncMethod();    // ❌ 不走代理
}
@Async
public void asyncMethod() { ... }
```

修法：拆类，让调用跨 Bean。

## 消息队列异步（Kafka / RabbitMQ）

消费者侧验证**只看副作用**（投影表更新、状态变更），不要直接抓消费者状态。`KafkaContainer` + `@ServiceConnection` + Awaitility 等投影表收到事件。

## Reactive（WebFlux）

用 Project Reactor 自带的 `StepVerifier`——它自带同步等待，**不需要** Awaitility。`.verify(Duration.ofSeconds(5))` 控超时。

## 反模式（项目内常见错误）

- ❌ `Thread.sleep(5000)` 等异步任务：套件耗时爆炸
- ❌ `await().atMost(60, SECONDS)`：超时上限给太宽
- ❌ `await().until(() -> condition)`：失败信息缺上下文
- ❌ `@Transactional` + Awaitility：子线程读不到数据，永远超时

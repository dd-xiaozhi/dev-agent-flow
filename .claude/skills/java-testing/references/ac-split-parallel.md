# AC-split 并行集成测试生成（testing adapter 内部模式）

> java-testing 作为 testing adapter 被 `/integration-test` 委托时，若 `spec.md §7` 的流程 AC 较多，把"写测试"按 AC 分组 fan-out 到多个 task subagent **并行编写**，再单次 `mvn verify` 汇总成一份 verdict.json。瓶颈在 LLM 逐方法串行生成，不在执行——并行只压缩生成墙钟，不改变验收语义。
>
> 本模式是 adapter 的**内部实现细节**：route.py 仍 → java-testing，verdict.json schema 不变，evaluator 仍只读单份聚合结果。

## 何时启用 / 何时跳过

| 条件 | 动作 |
|------|------|
| 去掉横切 AC 后，**单个 fixture family 内流程 AC > 4** | 启用 fan-out，按业务阶段分组并行写 |
| 单个 fixture family 内流程 AC ≤ 4 | 串行单文件（不值得 fan-out 开销） |
| 执行环境不支持嵌套 subagent | 自动降级串行，**绝不阻塞 Phase 2** |

## 6 步协议

```
spec.md §7（AC 清单）
  │
  ├─ Step 1  解析 + 分类：流程 AC vs 横切 AC
  ├─ Step 2  两级分组：先按 fixture family，再在重 family 内按业务阶段
  ├─ Step 3  【串行 prelude】每个重 fixture family 生成 1 个抽象支撑类 <Family>ITSupport
  ├─ Step 4  【并行 fan-out】每组 1 个 task subagent → 写 <Group>IntegrationTest extends 支撑类
  ├─ Step 5  【join】单次 mvn verify -Dit.test='*IntegrationTest' 编译并跑全部文件
  └─ Step 6  解析全部 failsafe XML → 聚合 verdict.json
```

**强制时序**：Step 3 prelude 必须先于 Step 4 fan-out 完成并落盘——grouped 文件 `extends` 支撑类才能编译。

## Step 1–2 分组算法

### 流程 AC vs 横切 AC

| 类别 | 识别特征（看 spec §7 `实现位置`） | 处置 |
|------|--------------------------------|------|
| **流程 AC** | 对应某个具体入口 / 步骤（解析 / 反查 / 主合并 / 渠道处理 / 通知） | 进业务阶段分组，各自有 `@Test` |
| **横切 AC** | "全链路写值断言" / "各分支 try-catch" / "统一审计 wrapper" / "横切关注点" | 不独立分组——落到**已 exercise 它的那个组**，作组内夹验断言或该组的专项方法 |

横切 AC 不需要独立 fixture，所以**跟随**它所贯穿的流程组，不单独 fan-out 一个 subagent。

### 两级分组

1. **先按 fixture family 切**：装配方式不同 = 不同 family，各自 self-contained。
   - HTTP 契约层（MockMvc standalone + mock service + 全局异常处理器）
   - 编排层（真实 SUT + mock 全部数据/外部依赖 + 真实入口驱动）
   - 每个 family 的 setUp 不可共用，必须分文件。
2. **再在重 family 内按业务阶段切**：同一 family 共享一套 fixture，按依赖阶段聚成 3~4 组（准备/反查 → 主流程写操作 → 横切+后置），每组一个文件 `extends` 同一支撑类。

## Step 3 — prelude 支撑类规格

每个**重 fixture family** 生成一个 `abstract <Family>ITSupport`，承载该 family 全部 fan-out 子文件的共享装配。来源：SUT 构造器依赖 + spec §7 引用的实体。

支撑类必含：

| 元素 | 说明 |
|------|------|
| mock 字段 | SUT 构造器的每个依赖一个 `mock(...)`（`protected`，供子类断言） |
| `@BeforeEach setUp()` | 装配 mock + new 出真实 SUT + family 级桩（如审计 `doAnswer` 真实执行被包裹动作、集合名 `@Document` 回放） |
| 工厂方法 | spec §7 涉及的 PO 构造（`protected`，子类复用） |
| 数据驱动 helper | 如 `buildExcel(...)` / `primeXxx()` 等公共前置 |
| 断言 helper | 如 `errOf(...)` 等跨方法复用的 matcher |

**Worked example — `SfMergeServiceITSupport`（编排层 family）**：
- 12 mock：`baseDao / mongoTemplate / dataflowMergeService / wxCpRobotUtil / dataOperationLogDao / bizErrorLogDao / unifyAccountDao / ecAccountDao / msAccountDao / wxMpUserDao / wecomContactDao / clsSfMappingService`
- 真实 `SfAccountMergeServiceImpl service`（12 参构造）
- family 桩：`dataOperationLogDao.execute(...)` doAnswer 真实跑 Runnable（AC-010 语义）；`baseDao.getCollectionName(@Document)` 真值回放
- helper：`primeSingleSlave / winnerUnify / slaveUnify / sfAccount / ecAccount / msAccount / wecomContact / errOf / buildExcel`

HTTP 契约 family 仅 AC-001（≤4），不建支撑类，保持 self-contained 单文件。

## Step 4 — fan-out subagent prompt 契约

执行 adapter 协议者（主 Claude）在**一条消息内并行发起多个 Agent 调用**，每组一个。subagent 类型用通用 task agent（`general-purpose`），**不用 `generator`**（保持 evaluator 侧独立）。

每个 subagent 的 prompt 必含：

- **输入**：本组 AC 子集（ID + `实现位置` + `建议集成测试方法名`，全部摘自 spec §7）；支撑类全限定名 + 它已提供的 mock/工厂/helper 清单；需读的生产源码路径（取方法签名用）。
- **约束（GAN 边界，逐条写进 prompt）**：
  - 只依据 **spec §7 + 生产源码** 推导测试；**禁止**读 Generator 的测试 / README / 解释性注释来判断或抄袭。
  - **禁止**重复定义 fixture——`extends <Family>ITSupport`，直接用继承来的 mock/helper。
  - 命名 `should_<期望>_When_AC<NNN>_<场景>`；HTTP 错误路径用断言三件套（status + Content-Type + `jsonPath("$.code")`）。
  - 横切 AC 在本组相关方法内夹验（如 `ArgumentCaptor` 校验 `sfid` 写入、`verify` 审计调用）。
- **输出（artifact-based-handoff）**：把 `<Group>IntegrationTest.java` 写到测试包；返回消息**只含文件路径 + `@Test` ↔ AC 映射**，不回贴代码。

## Step 5 — join：单次 mvn verify

全部子文件落盘后，adapter 在被测项目根跑一次：

```
mvn verify -DskipTests=false -Dit.test='*IntegrationTest'
```

失败也继续解析。一次性编译所有 grouped 文件 + 支撑类，能立即暴露跨文件不一致（子类引用了支撑类没有的 helper → 编译失败）。

## Step 6 — 聚合 verdict.json

解析 `target/failsafe-reports/TEST-*.xml`（全部文件），按 `integration-test/SKILL.md` 统一 schema 写单份 verdict.json：

| 字段 | 聚合方式 |
|------|---------|
| `totals.*` | 跨全部 testcase 累加 |
| `ac_coverage.passed_acs / failed_acs` | 全部方法名 `should_*_When_AC<NNN>_*` 反查 spec §7 |
| `failures[]` | 每个失败 testcase → `{ac, test_method, reason, severity:"major"}` |
| `verdict` | `failed+errors==0`→PASS；编译/上下文失败→ERROR；否则 FAIL |
| `meta.test_file_path` | 主支撑类路径 |
| `meta.test_files[]` | 全部分组文件 + 支撑类路径（可选） |

## 安全阀

| 阀 | 触发 | 动作 |
|----|------|------|
| 小 story 跳过 | family 内流程 AC ≤ 4 | 退回串行单文件 |
| 嵌套降级 | 执行环境不支持嵌套 subagent | 自动串行，不阻塞 Phase 2 |
| 编译/生成有界重试 | 某组文件不编译 / subagent 没产文件 | 对该组单独修复重试 ≤ 2 次；超限标 ERROR + 编译输出末 20 行 |

## 反模式

- ❌ 横切 AC（写值约束 / 审计 / 异常隔离）拆成独立 subagent——它们无独立 fixture，必须跟随流程组。
- ❌ grouped 文件各自重定义 mock / setUp——必须 `extends` 支撑类，否则 fixture 漂移。
- ❌ fan-out 前漏生成支撑类——子文件无法编译。
- ❌ 返回消息回贴整份测试代码——违反 artifact-based-handoff，只给路径。
- ❌ 跨 fixture family 强塞一个支撑类——HTTP 层与编排层装配不同，必须分 family。

## Worked example — SfAccountMerge 分组结果（无损分解）

| Fixture family | 组 | AC | `@Test` 方法 |
|----------------|----|----|-------------|
| HTTP 契约（self-contained，≤4 不 fan-out） | — | AC-001 | `should_return_400_When_AC001_FileEmpty` / `should_return_200_When_AC001_FilePresent` |
| 编排（`SfMergeServiceITSupport`） | B1 准备/反查 | AC-002 / AC-003 | `should_skip_invalid_rows_When_AC002_Parse` / `should_skip_and_log_When_AC003_SfAccountNotFound` |
| 编排 | B2 主合并+渠道（夹验 AC-004） | AC-004/005/006/007/008/009 | `should_update_master_and_audit_When_AC005_MasterMerge`（含 AC-004 夹验）/ `should_persist_sfid_When_AC004_AllDownstreamWrites` / `should_full_merge_ecms_When_AC006_AllSteps` / `should_mount_only_When_AC006_Boundary` / `should_delete_all_slave_records_and_audit_When_AC007` / `should_lightweight_merge_and_cls_sync_When_AC008` / `should_sync_afs_and_audit_When_AC009` |
| 编排 | B3 横切+通知 | AC-010 / AC-011 / AC-012 | `should_audit_all_mutations_When_AC010` / `should_isolate_errors_and_continue_When_AC011` / `should_push_wecom_notify_When_AC012` |

14 个方法全部落入唯一组；12 mock + 全部 helper 由 `SfMergeServiceITSupport` 覆盖；横切 AC-004 在 B2 夹验、AC-010/011 在 B3 共享编排 fixture——分解 lossless。

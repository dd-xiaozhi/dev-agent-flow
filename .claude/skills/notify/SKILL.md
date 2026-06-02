---
name: notify
description: Send structured notification to team IM channel (WeChat Work webhook) — project-aware / per-project install
disable-model-invocation: false
installed-from: agent-dev-standard@cf04193
adr-ref: ADR-005-skill-tier-semantics (notify = core / per-project / 每项目独立 SKILL.md 含 project-specific webhook + project_name)
---

# /notify — 团队消息通知

通过企业微信 Webhook 向团队 IM 渠道发送结构化消息。可被其他 skill 在关键节点调用。

**Project-aware:** 每个项目独立装一份 SKILL.md。install.sh 从 `<project>/docs/env.yaml`(或 `<project>/env.yaml`)读 `project.name` + `notify.qiwei_webhook` 替换 `Chopard-bde` + `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=c43a1730-bbee-4f7a-86a0-d54396b639ef` 占位符 / 装好后无占位符残留。

---

## 输入

- `$ARGUMENTS`:通知类型,可选值:
  - `release` — 发布通知(业务项目 / build + commit 清单)
  - `audit` — 审查完成通知(`/audit` 全量审查报告生成后)
  - `close` — Issue 关闭通知
  - `fix` — 分拣完成通知
  - `issue` — 今日 Issue 汇总(按 label 自动分类)
  - **`governance`** — Governance milestone 通知(元层项目 / ADR Accepted / 多 issue 闭环 broadcast)
  - **`qa-test`** — 转测通知(任务开发完成后通知 + @ QA 验收 / flow `notify-qa-test` 步骤调用)
  - `custom <message>` — 自定义消息

---

## 项目配置

- **webhook_url:** `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=c43a1730-bbee-4f7a-86a0-d54396b639ef`(install.sh 从 `<project>/docs/env.yaml notify.qiwei_webhook` 替换)
- **project_name:** `Chopard-bde`(install.sh 从 `<project>/docs/env.yaml project.name` 替换)

> 占位符 `{{...}}` 在 install.sh 装载时替换为项目实际值。装好后 SKILL.md 应无 `{{` 残留(per Module 02 安装时 sed substitution)。

---

## 消息模板

### release — 发布通知

**触发时机:** `/release` Step 6 后置处理

```bash
curl -s -X POST "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=c43a1730-bbee-4f7a-86a0-d54396b639ef" \
  -H "Content-Type: application/json" \
  -d '{
  "msgtype": "markdown",
  "markdown": {
    "content": "## 🐳 <font color=\"info\">Chopard-bde 发布通知</font>\n**环境:** <font color=\"info\">dev</font>\n**分支:** origin/<branch>\n**构建:** <font color=\"info\">#<build-number> SUCCESS</font>\n**时间:** <YYYY-MM-DD HH:MM>\n\n### 🐰 提交清单(<count> 个 commit)\n<逐行:commitId 简写 — msg>\n\n### 🐰 修复的问题\n<从 commit msg 中提取 Issue 编号,如 #55 #56>\n\n> <font color=\"comment\">🐱 请 FE/QA 关注本次变更</font>"
  }
}'
```

### audit — 审查完成通知

**触发时机:** `/audit` 全量审查报告生成后(仅高优先级发现 > 0 时触发)

```bash
curl -s -X POST "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=c43a1730-bbee-4f7a-86a0-d54396b639ef" \
  -H "Content-Type: application/json" \
  -d '{
  "msgtype": "markdown",
  "markdown": {
    "content": "## 🐧 <font color=\"warning\">Chopard-bde 审查报告</font>\n**轮次:** 第 <N> 轮\n**阶段:** <spec / architecture / api / behavior / integration>\n**日期:** <YYYY-MM-DD>\n\n### 🐧 统计\n- 总发现:<font color=\"warning\">**<total>**</font>\n- 缺失:<missing> · 偏差:<deviation> · 风险:<risk>\n- 🐰 高优先级:<font color=\"warning\"><high-count></font>\n- 🐰 回归:<regression-count>\n\n### 🦊 需要关注\n- 待修复(BE):<count>\n- 待确认(PM):<count>\n- 已排除:<count>\n\n> <font color=\"comment\">🐱 详见 docs/audit/<report-file></font>"
  }
}'
```

### close — Issue 关闭通知

**触发时机:** `/close` Step 4 关闭 Issue 后(手动 `/notify close` 触发 / 不自动)

```bash
curl -s -X POST "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=c43a1730-bbee-4f7a-86a0-d54396b639ef" \
  -H "Content-Type: application/json" \
  -d '{
  "msgtype": "markdown",
  "markdown": {
    "content": "## 🐰 Chopard-bde Issue 已关闭\n<font color=\"info\">**#<number>**</font> <title>\n**类型:** <gap/bug>\n**处理人:** BE\n\n### 🐼 决策摘要\n<一句话决策内容>\n\n### 🐰 关联更新\n- 共识文档:<font color=\"info\"><已更新 / 无需更新></font>\n- 模块文档:<已更新模块名>\n- commit:`<hash>`\n\n> <font color=\"comment\">🐱 该 Issue 已闭环</font>"
  }
}'
```

### fix — 分拣完成通知

**触发时机:** `/fix` Step 4 汇总后(手动 `/notify fix` 触发 / 不自动)

```bash
curl -s -X POST "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=c43a1730-bbee-4f7a-86a0-d54396b639ef" \
  -H "Content-Type: application/json" \
  -d '{
  "msgtype": "markdown",
  "markdown": {
    "content": "## 🐹 <font color=\"warning\">Chopard-bde 发现分拣完成</font>\n**来源:** <report-file>\n\n### 🐹 分拣结果\n- <font color=\"info\">🐰 文档直接修:<count></font>\n- <font color=\"warning\">🐰 转 Issue(代码):<count></font>\n- 🐰 转 Issue(等决策):<count>\n- <font color=\"comment\">🐰 标记排除:<count></font>\n\n### 🦊 需要关注\n<列出转 Issue 的高优先级项,含 Issue 编号>\n\n> <font color=\"comment\">🐱 代码修复请通过 /issue 处理</font>"
  }
}'
```

### issue — 今日 Issue 汇总

**触发时机:** 手动 `/notify issue`

**执行逻辑:**
1. 通过 GitHub API 拉取项目 issue tracker 全部 open Issues
2. 按 label 自动分类(沿用项目本地约定 / 若用 standard label-scheme 则按 [`concepts/label-scheme.md`](../../../../docs/docs/concepts/label-scheme.md) §3 状态机分类):
   - **BE 可关闭:** label 含 `be-confirmed`(已修复,待关闭)
   - **FE 负责:** label 含 `fe-` 前缀(FE 处理中)
   - **等 PM 确认:** label 含 `be-reviewed` 但无 `pm-reviewed`(等 PM 回复)
   - **BE 进行中:** label 含 `pm-reviewed` 但无 `be-confirmed`(BE 开发中)
   - **待分拣:** 其他(`state:open` 或无状态 label)
3. 组装消息并发送

```bash
curl -s -X POST "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=c43a1730-bbee-4f7a-86a0-d54396b639ef" \
  -H "Content-Type: application/json" \
  -d '{
  "msgtype": "markdown",
  "markdown": {
    "content": "## 🐰 Chopard-bde Issue 日报\n**日期:** <YYYY-MM-DD>\n**Open Issues:** <font color=\"info\"><total></font>\n\n### 🐼 BE 可关闭(<count>)\n<逐行:#N title>\n\n### 🦊 FE 负责(<count>)\n<逐行:#N title>\n\n### 🐧 等 PM 确认(<count>)\n<逐行:#N title>\n\n### 🐹 BE 进行中(<count>)\n<逐行:#N title>\n\n### 🐦 待分拣(<count>)\n<逐行:#N title>\n\n> <font color=\"comment\">🐱 分类依据:Issue label 状态</font>"
  }
}'
```

**空分类处理:** 某分类下无 Issue 时,该分类整段不出现在消息中(不显示空列表)。

### governance — Governance milestone 通知(元层项目 / standard 自身 dogfood)

**触发时机:** 手动 `/notify governance`(元层项目 / standard 自身 dogfood / ADR Accepted / 多 issue 闭环时手动触发)

**适用场景:**
- ADR Draft → Accepted 切换
- 一个 session / 一天内多 issue 闭环(如 ≥ 5 issue 同日 closed)
- 重要 governance 改动(label scheme / paradigm / pull sync 机制等)落地
- 团队 workflow 影响显著的设计层改动

**与 release 的区别:**
- `release` 聚焦 build / commit / FE-QA 协作(业务项目)
- `governance` 聚焦 governance milestone / ADR / 团队 workflow impact(元层项目)
- 致谢段对元层项目特别重要(reporter 提 issue 推动项目进化)

```bash
curl -s -X POST "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=c43a1730-bbee-4f7a-86a0-d54396b639ef" \
  -H "Content-Type: application/json" \
  -d '{
  "msgtype": "markdown",
  "markdown": {
    "content": "## 🐼 <font color=\"info\">Chopard-bde Governance 进展</font>\n**日期:** <YYYY-MM-DD>\n\n### 🐳 关键里程碑\n<逐行:milestone name + 简短 impact>\n\n### 🐰 Issue 进展(若有)\n- 闭环:<count> 个 / 含 <issue 编号列表 简写>\n- ADR Accepted:<count> 个 / 含 <ADR 编号 + 主题>\n\n### 🦊 团队影响\n<逐行:对团队 workflow 的关键 impact / 用人话短句>\n\n### 🐱 致谢\n<逐行 reporter / contributor — 排名不分先后 / 贡献不分大小>\n\n> <font color=\"comment\">🐱 详见 release-log / CHANGELOG [Unreleased] 段</font>"
  }
}'
```

### qa-test — 转测通知(+ @ QA)

**触发时机:** flow `notify-qa-test` 步骤(tapd-dev-complete 之后) / 手动 `/notify qa-test`

**⚠️ @ 机制(企微约束)**:企微 webhook 的 **markdown 消息不支持 @**,只有 `msgtype=text` + `mentioned_mobile_list`(手机号)能 @ 到人。故本类型**双发**:① markdown 富文本(转测内容)② text(@ QA)。

**执行逻辑(角色→手机号:经 team_roles 名字映射通讯录):**
1. 取 QA 成员名:读 `project-config.json.tapd.team_roles.qa`,每项取中文名(`"余琪(QiYu)"` → `余琪`)。
2. 查手机号:在扁平通讯录 `project-config.json.notify.qiwei_mentions`(`[{name, mobile}]`)里按 `name` 匹配上一步的名字,取其 `mobile`。`name` 仅用于映射/区分,**实际发送取 `mobile`**。提取非空 `mobile` 组成 `mentioned_mobile_list`。
3. 发 **markdown** 富文本(接口 + dev/uat 部署 + 质量 + 验收要点 + 工单链接)。
4. **若有非空 mobile** → 紧跟发一条 **text** 消息 `@ + 简短转测语`,带 `mentioned_mobile_list=<提取出的手机号数组>`(企微按手机号匹配群成员 @)。
5. **若 mobile 全为空** → 跳过 step 4 的 @,仅发 markdown,并 WARN:`QA 成员(<列出名字>)在 qiwei_mentions 的 mobile 未填,跳过 @,请在 project-config.json 补手机号`(不阻断 flow)。

> 通用化:@ 任意角色 = 取 `team_roles.<role>` 名字 → 通讯录查 mobile。通讯录只按名字维护一份,不重复角色结构。

```bash
# ① markdown 富文本(转测内容)
curl -s -X POST "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=c43a1730-bbee-4f7a-86a0-d54396b639ef" \
  -H "Content-Type: application/json" \
  -d '{
  "msgtype": "markdown",
  "markdown": {
    "content": "## 🐳 <font color=\"info\">Chopard-bde 转测通知 · 请 QA 验收</font>\n**需求:** <需求标题>\n**状态:** <font color=\"info\">已实现 → 待验收</font>\n\n### 🐰 接口\n`<METHOD> <path>`(<入参说明>)\n\n### 🐰 部署\ndev #<build> SUCCESS · uat #<build> SUCCESS\n\n### 🦊 验收要点\n<逐行验收点>\n\n> <font color=\"comment\">🐱 详见 TAPD 工单 <ticket_id></font>"
  }
}'

# ② text + @ QA(仅当 qiwei_mentions.qa 非空;mentioned_mobile_list 取该数组)
curl -s -X POST "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=c43a1730-bbee-4f7a-86a0-d54396b639ef" \
  -H "Content-Type: application/json" \
  -d '{
  "msgtype": "text",
  "text": {
    "content": "请验收上述需求:<需求标题>(已部署 dev/uat)",
    "mentioned_mobile_list": ["<QA手机号1>", "<QA手机号2>"]
  }
}'
```

> 通讯录:`project-config.json.notify.qiwei_mentions` = 扁平 `[{name, mobile}]`(已 gitignore,不入仓)。角色成员名取自 `tapd.team_roles.<role>`,按 `name` 在通讯录查 `mobile`。发送取 `mobile`,全空则只发 markdown 不 @。

### custom — 自定义消息

**触发时机:** 手动 `/notify custom <message>`

```bash
curl -s -X POST "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=c43a1730-bbee-4f7a-86a0-d54396b639ef" \
  -H "Content-Type: application/json" \
  -d '{
  "msgtype": "markdown",
  "markdown": {
    "content": "## 🐦 Chopard-bde\n<message>\n\n> <font color=\"comment\">🐱 <YYYY-MM-DD HH:MM></font>"
  }
}'
```

---

## 执行逻辑

### Step 1 — 组装消息

根据通知类型 / 从当前上下文中提取信息填充对应模板:

- **release** — 从 Jenkins(或 CI/CD)构建结果 + 提交清单 + problem-registry 提取
- **audit** — 从审查报告统计提取(仅高优先级发现 > 0 时触发)
- **close** — 从 Issue 关闭事件 + commit hash + 文档同步状态提取
- **fix** — 从 `/fix` 分拣输出提取
- **issue** — 通过 GitHub API 拉取 open Issues / 按 label 自动分类后填充
- **governance** — 从 release-log + CHANGELOG `[Unreleased]` + Issue closed 列表 + ADR Accepted 列表组装(适用元层 dogfood 场景)
- **custom** — 直接使用用户提供的消息

### Step 2 — 发送

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=c43a1730-bbee-4f7a-86a0-d54396b639ef" \
  -H "Content-Type: application/json" \
  -d '<json-payload>'
```

- HTTP 200 + `{"errcode":0,"errmsg":"ok"}` → 发送成功
- 其他 → 报错,展示响应内容(不阻断主流程)

### Step 3 — 记录

在当前操作的输出中标注"已通知团队"。

---

## 被其他 Skill 调用的场景

| Skill | 调用时机 | 通知类型 | 触发条件 |
|---|---|---|---|
| `/release` | Step 6 后置处理 | release | **按门槛判断** — 语义优先(feat/fix/perf/BREAKING 必发)/ 阈值兜底(commit ≥ 3 发)/ 30 分钟内合并 |
| `/audit` | 全量审查完成后 | audit | **条件触发** — 仅高优先级发现 > 0 时发送 |
| `tapd-full` flow `notify-qa-test` 步骤 | tapd-dev-complete 之后(任务开发完成+部署后) | qa-test | **总是发** — QA 是明确收件人 + 行动项(验收),符合推送纪律"✅ 可推";@ QA 走 mentioned_mobile_list(QA 名取 `team_roles.qa` → 通讯录 `qiwei_mentions` 查 mobile,空则仅 markdown) |

**以下场景不自动通知:**

- `/close` — GitHub Issue 本身有通知机制 / 不重复
- `/fix` — 内部分拣 / 对方不需要行动 / 等 release 时汇总
- `issue` — 人工触发 / 按需了解全局 Issue 状态
- `governance` — 元层 dogfood / 手动触发 / 不在常规 skill 调用链

> `disable-model-invocation: false` — 允许其他 skill 执行时自动触发通知 / 不需要用户手动输入 `/notify`。

---

## 约束

- **Webhook URL 不在消息内容或日志中输出**(security / 防泄露)
- **通知失败不阻断主流程** — 通知是辅助 / 不是关键路径
- 消息使用 markdown 格式 / 保持简洁可读
- **只在需要对方行动时才发通知** — 信息同步不等于需要通知 / 避免噪音
- `close` / `fix` 模板保留但不自动触发 / 需要时通过 `/notify close` / `/notify fix` 手动发送
- `governance` 模板专用元层项目(standard 自身 dogfood)/ 业务项目不主动触发

---

## 美学约定(借鉴 + 沉淀)

| 元素 | 用法 | 含义 |
|---|---|---|
| 🐳 鲸鱼 | 标题图标(release 类)| 蓝色 / 明亮 / 积极 |
| 🐰 兔子 | 二级图标(数据项)| 白色 / 双模式高可见 |
| 🐱 猫咪 | 引导语图标(末尾 > 引用)| 黄色 / 提醒动作 |
| 🐧 企鹅 | 标题图标(audit 类)| 黑白高对比 |
| 🦊 狐狸 | 二级图标(需要关注)| 橙色 / 提醒 |
| 🐼 熊猫 | 标题图标(governance / close 类)| 黑白对比 / 元层稳重 |
| 🐹 仓鼠 | 标题图标(fix 类)| 工作仓库感 |
| 🐦 小鸟 | 标题图标(custom)| 轻快 / 通用 |
| `<font color="info">` | 中性信息 | 绿色 / 积极 |
| `<font color="warning">` | 需要关注 | 橙色 / 引起注意 |
| `<font color="comment">` | 末尾 > 引用 | 灰色 / 辅助提示 |

**美学原则:**
- 短句 > 长段落(IM 阅读场景)
- 动物 emoji 区分消息类型(扫一眼知是 release / audit / governance)
- `<font color>` 标签限定关键信息(总数 / 高优先级 / 警示)
- 末尾 `> <font color="comment">` 引用作为收尾(避免信息长尾噪声)
- 致谢段(governance template)— 列全 contributor / 排名不分先后 / 贡献不分大小

---

## 推送纪律(notify-discipline)

**推送基于人性 / 默认是"不打扰" / 按场景判据决定是否发 / 不要为发而发。**

注意力是稀缺资源。spool / release-log / CHANGELOG / Issue 状态变化 / commit history 都能让关注的人主动查 / 不需要被实时打扰。频繁推送制造"还有事没处理完"的紧迫感 / 反而压低团队整体效能;推得多 = 重要信号被稀释。

### 场景判据表

| 场景 | 推送? | 理由 |
|---|---|---|
| 内部 SOP / concept / rule / protocol 升级 | ❌ 不推 | 关注的人自己看 release-log / spool |
| PP / registry / 内部档案落档 | ❌ 不推 | 纯内部追溯 |
| 内部 triage / 路由 / 分流动作 | ❌ 不推 | 协作动作 / 不打扰 |
| Issue close 含**外部 contributor** 致谢 | ✅ 可推(克制) | 给反馈源认可 / 限单条 / 不带营销语 |
| **阻塞性** bug fix / 安全发现 / 需团队立即知情(明确收件人 + 行动项) | ✅ 可推 | 打断成本 < 沉底成本 |
| 周末 / 节假日的日频任务 | ❌ 不推 | 工作日才有 dev 状态 / 协作礼貌 |
| 业务发布 `/release` 通知(build 号 + commit 清单) | ✅ 推(项目内已有惯例) | QA / FE 等待回测的明确收件人 |
| **handoff / skill 模板默认塞 notify step** | ❌ 应**删除** / 改为按判据决定 | 反习惯性套用 |

### 反模式(已实证)

- ❌ Handoff / skill 模板每个都默认带 notify step(SA 习惯性套用 / 2026-05-28 batch 实证:同批 3 handoff 各发 1 次企微 / 共 3 次打扰)
- ❌ `governance` template 推内部 PP 落档 / 内部 concept 升级(5-28 B-1 / B-3 实证)
- ❌ `close` template 推非外部 contributor 的内部 close(5-28 B-2 实证 / #24 是内部 surface)
- ❌ "做了大事就发一条" — 不是大事 = 不该推 / 是大事 = 关注的人有别的更准的渠道(spool / release-log / Issue label 变化 / git history)

### 起 handoff / skill 时的 SOP(防 notify 误用)

1. **不要**默认放 "Step N — 企微通知(`notify` skill)" 在 handoff / skill 模板内
2. 真需要推的场景 / 在 handoff / skill 内显式写 "推送判据 + 收件人 + 用哪个 template + 触发条件" 而不是只标"发通知"
3. 多 handoff batch 处理时 / **至多** 1 条 batch-level 通知 / 不每个 handoff 各推一条
4. 失败后亡羊补牢:已发的不能撤,但 spool + active-observation-period-tracker(SA 侧)留实证防下次同模式

### 关联

- 本段 source:2026-05-28 spool-review surface 处置批次 incident(B-1/B-2/B-3 共 3 次企微 / 用户拦截)
- 关联 user ecosystem feedback:同 SA 在 user memory 落 `feedback_notify_discipline.md`(参考 / 不引绝对路径)
- 升级路径:等跨项目 ≥ 1 case 复现 → SA 派 backflow 升 rule 母巢 / 现阶段守 standard 内 notify SKILL.md 自规约即可

---

## 修订日志

| 日期 | 修订 | 责任人 |
|---|---|---|
| 2026-05-28 | 加 §推送纪律(notify-discipline)段 — 铁律 + 场景判据表 8 行 + 反模式 4 项 + handoff/skill SOP 4 项 + 关联 / source: 5-28 spool-review surface 处置批次 incident(B-1+B-2+B-3 共 3 次企微打扰 / 用户拦截) | standard EL via SA handoff `2026-05-28-notify-discipline-skill-upgrade.md`(B-4)|

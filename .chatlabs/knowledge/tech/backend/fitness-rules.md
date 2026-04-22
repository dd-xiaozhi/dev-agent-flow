---
name: backend-fitness-rules
description: 后端架构适应度函数清单。fitness-run skill 和 generator 在编码/提交前必须运行这些检查。
---

# 后端架构适应度函数

> 架构规则是防止技术债积累的最后防线。每次引入违规前权衡，引入后立刻修复。
> 本文件是 `.chatlabs/knowledge/README.md` 定义的模块规范，供 fitness-run skill 和 generator 读取。

---

## 一、已实现的检查（fitness/*.sh）

| 规则名              | 检查内容                                          | 运行时机                  |
|-------------------|-----------------------------------------------|------------------------|
| `layer-boundary.sh` | Controller/Service/Repository 三层依赖方向正确 | 每次文件变更前              |
| `openapi-lint.sh`   | openapi.yaml 合法 + 与代码 endpoint 一致        | 修改 endpoint 后          |
| `dep-scan.sh`        | 禁止循环依赖、包依赖方向正确                    | 每次依赖变更后              |
| `contract-drift-check.py` | contract.md ↔ openapi.yaml 一致性   | frozen 后提交前           |

---

## 二、Layer Boundary 规则

```
controller → service → repository → domain
                  ↕
              config / exception（允许）

禁止：
  controller → repository（绕过 service）
  service → controller（循环）
  repository → service（依赖倒置错误）
```

---

## 三、注释规范（可检查）

`hooks/post-tool-linter-feedback.py` 检测以下违规模式：

| 违规模式          | 正则                              | 正确做法                     |
|----------------|--------------------------------|--------------------------|
| CASE 编号注释     | `CASE-\d+`                       | 删除，流程信息在 `cases/*.md` |
| `@author` / `@since` | `@author\|@since\|@last-modified` | 删除，git blame 已记录    |
| 人工 TODO/FIXME   | `TODO\|FIXME\|HACK`              | 写入 tech-debt-backlog.md   |

---

## 四、fitness-backlog 追加规则

以下情况修复后必须向 `docs/fitness-backlog.md` 追加候选规则：

1. **规则缺失**：错误根因是没有对应 fitness 规则 → 追加候选。
2. **规则粒度不够**：现有规则无法捕获该错误模式 → 改进候选。
3. **工具问题**：fitness 工具本身 bug → 追加 tech-debt-backlog 条目（不是 fitness 规则）。

---

## 五、失败处理

| 场景           | 处理方式                                    |
|---------------|-----------------------------------------|
| 单个 fitness 失败 | 停止当前操作，修复后再继续                   |
| 多个 fitness 失败 | 按优先级修（层级→契约→依赖），修完一个跑一次确认 |
| 新错误无对应规则  | 修复 + 向 `docs/fitness-backlog.md` 追加候选规则  |

---

## 六、TBD

- [ ] TBD: 确认 `layer-boundary.sh` 的检查逻辑是否覆盖了当前包结构（可能需调整 `grep` 模式）
- [ ] TBD: 确认是否有其他项目特定的 fitness 规则（如禁止某库使用、禁止某模式）

---

## 关联

- Fitness 检查脚本：`.claude/fitness/*.sh`
- Fitness backlog：`docs/fitness-backlog.md`
- 编码风格：`backend/coding-style.md`
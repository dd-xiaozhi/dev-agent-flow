# Evals — golden task 回归基线

> **定位**：改 agent prompt / flow 模板后的回归守护。用**要点清单核对**（非全文 diff）验证产出质量不退化。
>
> **为什么要点清单而非 diff**：LLM 产出非确定，全文 diff 无意义。但"该出现的字段/端点/决策是否出现、该禁止的越界是否出现"是确定的、可机器核验的。

## 结构

```
evals/
├── README.md
├── run_eval.py                    # harness：要点清单核对
└── golden/
    └── <id>/
        ├── manifest.json          # 断言清单（must_contain / must_not_contain）
        ├── input/                 # 需求素材（喂给 flow 的 description）
        └── expected/              # 冻结的参考产物（供 selftest + 人工对照）
```

## 用法

```bash
# 列出所有 golden task
python evals/run_eval.py list

# 自检：用 expected/ 作 produced，证明 harness + manifest 自洽（framework 仓常驻可跑）
python evals/run_eval.py selftest --all
python evals/run_eval.py selftest g1-contract-quality

# 真实回归：跑完 flow 后核对产出
python evals/run_eval.py run g1-contract-quality --produced docs/task/store/<story_id>
```

## 回归工作流

改 agent prompt / flow 模板前后各跑一次：

1. 用 `golden/<id>/input/` 的 description 启动对应 flow（`/story-start` 等）
2. 跑到目标产物节点（如 contract.md / spec.md / verdict.json）
3. `run_eval.py run <id> --produced <task_dir>` 核对要点
4. 对比改动前后的 PASS/FAIL——退化即被捕获

## 加新 golden task

1. 建 `golden/<id>/`，写 `manifest.json`（见下方 schema）
2. `input/` 放需求素材，`expected/` 放一份满足断言的参考产物
3. `run_eval.py selftest <id>` 确认 expected/ 通过自己的断言（manifest 自洽）

### manifest.json schema

```json
{
  "id": "g1-contract-quality",
  "description": "校验 doc-librarian 产出 contract.md 要点齐全 + 无越界",
  "flow_id": "local-spec",
  "target_artifact": "contract.md",
  "assertions": {
    "must_contain":     [{"name": "含验收条件", "pattern": "验收条件|AC-\\d+"}],
    "must_not_contain": [{"name": "契约不含技术实现(越界 planner)", "pattern": "@RestController|CREATE TABLE"}]
  }
}
```

- `pattern` 是 Python 正则，对 artifact 全文 `re.search`
- `must_contain` 找不到 = FAIL；`must_not_contain` 找到 = FAIL（越界）
- 每条断言可选 `artifact` 覆盖 `target_artifact`（跨产物核对）

## 设计原则

- **断言测的是"约束满足"，不是"文字相同"**——对齐 spec-to-code-flow 的验收条件/硬约束思路
- **selftest 是自洽底线**——expected/ 必须通过自己的断言，否则 manifest 写错了
- **要点清单从约束推导**——每条断言对应一个 spec 硬约束 / agent 职责边界，不是随意抓字符串

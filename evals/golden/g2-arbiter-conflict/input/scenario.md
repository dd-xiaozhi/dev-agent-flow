# 场景 — 预埋跨 story API 路径冲突（测 arbiter C2 拦截）

## 前置：registry 预埋一条历史记录

跑本 golden 前，向 `docs/registry/api.jsonl` 追加一条**他人 story** 的活跃记录：

```json
{"story_id":"existing-account","method":"POST","path":"/api/v1/auth/login","status":"active","owner_task":"existing-account","ts":"2026-06-01T00:00:00+08:00"}
```

## 新 story 需求（喂给 flow）

新需求「第三方登录」的 spec 又要注册 `POST /api/v1/auth/login`（与历史活跃记录同 method+path）。

## 期望 arbiter 行为

arbiter 读 registry（scoped 查询 `api --path-prefix /api/v1/auth --exclude-story <新 story>` 或小表全读）后，应：

- 检出 C2 路径冲突（同 method+path 且 status=active 的非自身记录）
- verdict = CONFLICT
- rollback_to = planner（改路径或合并端点）
- 产出 `verdict.json` + `arbitration-report.md`

## 核对

```bash
python evals/run_eval.py run g2-arbiter-conflict --produced docs/reports/arbitration/<新 story_id>
```

> **注**：本 golden 需真实跑 arbiter agent 产出 verdict.json 才能 `run` 核对（无 expected/ 供 selftest——
> verdict.json 由 arbiter 动态产出，不预置参考件）。断言核对的是 arbiter 的**判定结果**（CONFLICT + C2 + rollback），
> 这是确定的，不受 LLM 措辞影响。清理：核对后从 api.jsonl 删除预埋行，避免污染后续。

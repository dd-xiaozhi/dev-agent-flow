# Principle 3: Information Hiding

Each module should encapsulate design decisions. When the same knowledge appears in multiple modules, information has leaked.

## Common Leakage Patterns

**JSON schema knowledge scattered**:
```python
# BAD — every caller iterates + parses task.json independently
# GOOD — one module owns it:
def iter_active_tasks(tasks_dir: Path) -> Iterator[TaskInfo]:
    """Yield all active (non-archived) tasks."""
    ...
```

**File format leaking through layers**:
```python
# BAD — caller knows it's JSON + path convention
data = json.loads((trellis_dir / "registry.json").read_text())
data["agents"][agent_id] = {...}

# GOOD — module hides storage format
registry = AgentRegistry(trellis_dir)
registry.add(agent_id, task=task_name, platform="claude")
```

## 项目对应实践

本项目内 `task_store.py` 就是 information hiding 的成熟实例 —— 所有 task.json 读写过它,其他脚本不应直接 `json.loads(task.json)`。

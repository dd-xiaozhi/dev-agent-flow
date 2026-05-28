# Principle 1: Deep Modules

A module's value is the ratio of functionality hidden vs. interface exposed.

```
Deep module (good):          Shallow module (bad):
┌──────────┐                 ┌──────────────────────────┐
│ simple   │                 │ complex interface        │
│ interface│                 │ many params, many methods │
├──────────┤                 ├──────────────────────────┤
│          │                 │                          │
│  rich    │                 │  thin implementation     │
│  impl    │                 │                          │
│          │                 └──────────────────────────┘
│          │
└──────────┘
```

**Practical test**: If a caller must understand how the module works internally to use it correctly, the module is too shallow.

## Example: Task Data Access

```python
# Shallow — every caller must know JSON shape + paths + defaults
data = json.loads((tasks_dir / name / "task.json").read_text())
title = data.get("title") or data.get("name", "")
status = data.get("status", "planning")
```

```python
# Deep — caller gets typed data, module hides JSON/path/parsing/defaults
@dataclass(frozen=True)
class TaskInfo:
    name: str
    title: str
    status: str
    directory: Path

def load_task(tasks_dir: Path, name: str) -> TaskInfo | None: ...
def list_active_tasks(tasks_dir: Path) -> list[TaskInfo]: ...
```

The deep version absorbs JSON parsing, field defaults, directory scanning, archive filtering. Callers work with typed data.

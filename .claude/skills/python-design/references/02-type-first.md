# Principle 2: Type-First Development

Types define contracts before implementation. This workflow catches design problems early:

1. **Define data shapes** — dataclass or TypedDict first
2. **Define function signatures** — parameter and return types
3. **Implement to satisfy types** — let the type checker guide completeness
4. **Validate at boundaries** — runtime checks only where data enters the system

## Frozen Dataclasses for Internal Data

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class AgentRecord:
    agent_id: str
    task_name: str
    worktree_path: Path
    platform: Literal["claude", "codex", "cursor"]
    status: Literal["running", "done", "failed"]
    branch: str
```

Frozen dataclasses are immutable — no accidental mutation, safe to pass around.

## TypedDict for External JSON Shapes

When the data comes from a file (task.json, config.yaml, registry.json), use TypedDict to document the expected shape:

```python
from typing import TypedDict, Required, NotRequired

class TaskData(TypedDict):
    title: Required[str]
    status: Required[str]
    assignee: NotRequired[str]
    priority: NotRequired[str]
    parent: NotRequired[str]
    children: NotRequired[list[str]]
```

This eliminates scattered `.get("field", default)` calls — the shape is documented once.

## NewType for Domain Primitives

When two strings mean different things, make the type system enforce it:

```python
from typing import NewType

TaskName = NewType("TaskName", str)    # directory name like "03-10-v040"
BranchName = NewType("BranchName", str)  # git branch like "feat/v0.4.0"

def create_branch(task: TaskName) -> BranchName:
    return BranchName(f"task/{task}")
```

## Discriminated Unions for State

When an entity has distinct states with different data:

```python
@dataclass(frozen=True)
class Pending: status: Literal["pending"] = "pending"

@dataclass(frozen=True)
class Running:
    status: Literal["running"] = "running"
    pid: int
    worktree: Path

@dataclass(frozen=True)
class Completed:
    status: Literal["completed"] = "completed"
    branch: str
    commit: str

AgentState = Pending | Running | Completed

def handle(state: AgentState) -> None:
    match state:
        case Running(pid=pid): check_process(pid)
        case Completed(branch=br): create_pr(br)
        case Pending(): pass
```

The type checker ensures every state is handled.

# Principle 4 + 5: Complexity Management

## Principle 4: Pull Complexity Downward

When complexity is unavoidable, the module should absorb it internally rather than pushing it to callers. A module has few developers but many users — it's better for the module author to handle complexity once than for every caller to handle it independently.

```python
# BAD — every caller checks returncode, decodes stderr, handles encoding
def run_git(args: list[str]) -> subprocess.CompletedProcess: ...

# GOOD — absorbs complexity, raises typed error
def run_git(args: list[str], *, cwd: Path | None = None) -> str:
    """Run git command, return stdout. Raises GitError on failure."""
    result = subprocess.run(["git"] + args, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", cwd=cwd)
    if result.returncode != 0:
        raise GitError(args[0], result.stderr.strip())
    return result.stdout.strip()
```

### Anti-patterns of Pushing Complexity Up

- Returning raw `subprocess.CompletedProcess` and letting callers check `.returncode`
- Raising generic exceptions that callers must parse
- Using configuration parameters to avoid making decisions
- Returning `dict` when a typed object would let callers skip validation

---

## Principle 5: Define Errors Out of Existence

Exception handling is a major source of complexity. The best strategy is to design semantics so error conditions simply aren't errors.

```python
# BAD — preconditions force callers to guard:
def remove_agent(registry, agent_id):
    if agent_id not in registry["agents"]:
        raise KeyError(...)
    del registry["agents"][agent_id]

def init_workspace(path):
    if path.exists():
        raise FileExistsError(...)
    path.mkdir()

# GOOD — postconditions: define by what's true after the call
def remove_agent(registry, agent_id):
    """Ensure agent_id is not in registry after this call."""
    registry["agents"].pop(agent_id, None)

def ensure_workspace(path: Path) -> Path:
    """Ensure workspace directory exists."""
    path.mkdir(parents=True, exist_ok=True)
    return path
```

**Key insight**: define operations by **postcondition** ("after this call, X is true") rather than precondition ("X must be true before calling").

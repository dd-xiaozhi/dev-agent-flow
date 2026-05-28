# Principle 8 + 9: Infrastructure & Parsing

## Principle 8: Consistent Shared Infrastructure

When multiple scripts need the same capability, provide it once in `common/`.

| Capability | Should Live In | Not In |
|-----------|---------------|--------|
| JSON file read/write | `common/io.py` | Each script's `_read_json_file` |
| Terminal colors + logging | `common/log.py` | Each script's `Colors` class |
| Git command execution | `common/git.py` | `_run_git_command` prefixed private |
| Task data access | `common/tasks.py` | Ad-hoc task.json parsing |
| Path constants | `common/paths.py` (existing) | Hardcoded strings |

**项目对应实践**：本项目用 `.claude/scripts/paths.py` 和 `.claude/scripts/task_store.py` 作为共享基础设施 —— 所有 skill 的 scripts 都通过 `sys.path.insert + from paths import` 复用,不自己拼 path。

**Naming**: If a function is used by other modules, it's public API — don't prefix it with `_`.

---

## Principle 9: Structured CLI Output Parsing

When parsing output from shell commands (git, grep, etc.), respect semantic whitespace:

```python
# BAD — .strip() destroys semantic whitespace
# git submodule status prefix: ' ' = initialized, '-' = uninitialized, '+' = changed
line = output_line.strip()  # Loses the prefix character!

# GOOD — strip only trailing newlines
line = output_line.rstrip("\n\r")
prefix = line[0] if line else " "
```

Always document what each field position means when parsing structured command output.

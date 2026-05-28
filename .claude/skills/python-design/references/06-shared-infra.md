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

**项目对应实践**：本项目把**业务逻辑**类共享基础设施集中在 `.claude/skills/task/scripts/`(`task_store.py` task.json 门面 + `task_index.py` 索引工具)—— 它们通过单行 `sys.path.insert(0, parents[3] / "skills" / "task" / "scripts")` 复用。

> **例外**：路径常量本项目**未集中管理**(无 paths.py)—— 每个脚本在顶部自行计算 `PROJECT_DIR` 再拼接子路径。这是项目特定的工程权衡(避免一个 SSOT 影响过多文件 sys.path 链路),不代表"路径硬编码"是普适最佳实践。

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

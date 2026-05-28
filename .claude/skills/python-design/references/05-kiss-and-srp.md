# Principle 6 + 7: Simplicity & Boundaries

## Principle 6: KISS and Rule of Three

### KISS — Keep It Simple

Choose the simplest solution that works. Complexity must be justified by concrete (not hypothetical) requirements.

```python
# Over-engineered — registry pattern for 3 formatters (class hierarchy, decorators)
# Simple — just a dictionary
FORMATTERS = {"json": format_json, "text": format_text, "table": format_table}

def format_output(fmt: str, data: Any) -> str:
    formatter = FORMATTERS.get(fmt)
    if not formatter:
        raise ValueError(f"Unknown format: {fmt}")
    return formatter(data)
```

### Rule of Three

Wait until you have **three** instances of a pattern before extracting an abstraction. Two is coincidence; three is a pattern. Premature abstraction is worse than duplication because:

- It couples unrelated code through a shared abstraction
- It makes each instance harder to understand independently
- It creates pressure to fit future cases into the abstraction even when they don't fit

**However**: when you do hit three, extract immediately. Don't let it reach nine.

---

## Principle 7: Single Responsibility and Module Boundaries

Each module should have **one reason to change**. When a module grows beyond ~300 lines, check if it has multiple responsibilities.

### Decomposition Signals

Split when:
- A file has multiple "sections" separated by comment headers
- You need to import only one function from a large module
- Tests for different parts of the module have no shared setup
- Changes to one responsibility don't require understanding the other

### How to Split

Split by **information hiding** (what knowledge is encapsulated), not by execution order (what runs when).

```python
# BAD — split by execution order (temporal decomposition)
# step1_parse_args.py, step2_validate.py, step3_execute.py
# All three must know the command structure

# GOOD — split by responsibility
# task_store.py    — owns task.json read/write, schema, iteration
# task_cli.py      — owns argparse, subcommand routing
# task_display.py  — owns formatting, colors, table output
```

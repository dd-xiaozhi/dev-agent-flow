# Red Flags Quick Reference

Code review 和 self-review 时按这张表对照 diff。

| Signal | What It Means |
|--------|--------------|
| **Shallow Module** | Interface is nearly as complex as implementation |
| **Information Leakage** | Same JSON schema / file format knowledge in multiple modules |
| **Duplicated Utility** | Same helper function copied to multiple files |
| **God Module** | File > 500 lines with multiple unrelated responsibilities |
| **Pass-Through Function** | Function just forwards args to another with similar signature |
| **Magic `.get()` Chains** | `data.get("x") or data.get("y", "")` — missing type definition |
| **sys.path Hacking** | `sys.path.insert(0, ...)` — fix package structure instead |
| **Private-Named Public API** | `_function` imported by 3+ external modules |
| **Raw Dict Threading** | Passing `dict` through 4+ function calls — use a dataclass |
| **Repeated Iteration** | Same directory scan / file parse pattern in 3+ locations |
| **Broad Exception Catch** | `except Exception:` without re-raising — hides bugs |
| **Temporal Decomposition** | Modules split by "what runs when" instead of "what knows what" |

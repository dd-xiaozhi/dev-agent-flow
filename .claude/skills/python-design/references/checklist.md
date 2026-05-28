# Design Checklist

## 写代码前

1. **Types first**: Define the data shape before writing logic
2. **Module depth check**: Will the interface be simpler than the implementation?
3. **Duplication scan**: `grep -r "pattern" .` before creating new utilities
4. **Responsibility check**: Does this belong in an existing module?
5. **Error design**: Can you define the error out of existence?
6. **Naming precision**: Does the name convey meaning without reading the implementation?

## Code Review 中

1. **Red flags scan**: Check the [red-flags.md](red-flags.md) table against the diff
2. **Type safety**: Are new data shapes documented with types?
3. **Information hiding**: Does the change leak implementation details?
4. **Consistency**: Does it follow the existing patterns in the module?
5. **Depth**: Is the common path simple for callers?

## 战略投入提醒

Spend roughly **10-20% of each change** improving surrounding design.

Working code is necessary but not sufficient. The increments of software development should be **abstractions**, not just features. Each change should leave the codebase slightly better than you found it.

This is not perfectionism — it's compound interest. Small design improvements accumulate into a system that's dramatically easier to work with over time.

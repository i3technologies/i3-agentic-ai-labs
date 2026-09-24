# Definition of Done — Task Closure Checklist

Every Bob task MUST finish with every item below confirmed. Do not mark a task complete until
all checkboxes can be ticked. Record evidence (file paths, test output, commit refs) inline
against each item where applicable.

```text
[ ] Scope identified
[ ] Hard constraints checked (HC-1 → HC-8)
[ ] Dependencies identified
[ ] Existing tests inspected
[ ] Code changed only within approved scope
[ ] Unit tests added/updated
[ ] Integration tests added/updated where applicable
[ ] Security checks executed
[ ] Tenant isolation checked
[ ] Agent risk tier checked where applicable
[ ] Observability checked
[ ] Migration/rollback checked
[ ] Documentation updated
[ ] Git diff reviewed
[ ] Acceptance criteria passed
[ ] Evidence recorded
```

**Source:** §11 of `i3-IBM-Bob-Technical-Implementation-Guide.md` (master engineering execution guide).

## Enforcement notes

- Bob must surface this checklist at the end of every task response or task-closure summary.
- Any item that is N/A for a given task must be explicitly stated as N/A with a one-line
  rationale (e.g. "Migration/rollback — N/A: config-only change, no schema migrations").
- A task is **BLOCKED** (not done) if any item is unchecked without an N/A rationale.
- The checklist may not be skipped for "small" tasks. Scope and HC checks are mandatory even
  for single-line changes.

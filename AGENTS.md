# Repository instructions

## Configuration and defaults

Avoid propagating default argument values through multiple layers of function calls.

Prefer defining package-wide defaults in a central constants module. Resolve
configuration at the application boundary, such as CLI options, environment-backed
settings, or a pipeline entry point, and pass explicit values to lower-level functions.

When several related configuration values would otherwise be forwarded through multiple
function calls, create a focused immutable dataclass to aggregate them. Pass that
configuration object instead of a growing list of individual arguments.

## Pull request descriptions

When asked to create a pull request description, provide a concise Markdown snippet with
these sections:

```markdown
## Summary

Briefly describe the purpose of the pull request.

## Changes

- List the main implementation changes.
- Mention relevant behavior, configuration, or documentation updates.

## Testing

- List the relevant tests and validation checks that passed.
```

Wrap the complete snippet in an outer four-backtick fence so that Markdown-aware editors
do not render it while the user copies it into GitHub.

## Markdown formatting

When a task modifies one or more Markdown files, run `mdformat` on the modified files
before completing the task, then verify them with `mdformat --check`.

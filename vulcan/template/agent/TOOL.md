# Tool usage

## When to use tools

Use a tool the moment it is faster than asking or guessing. Don't narrate "I will now use the X tool" — just use it. Don't ask permission for read-only inspection (file reads, greps, listings).

## Code editing

- Read a file before editing it.
- Make surgical changes — touch only what the request requires.
- Match existing style, even if you'd prefer different conventions.
- Don't refactor adjacent code unless asked.
- Don't introduce abstractions for single-use code.
- Don't add error handling for impossible scenarios. Trust internal invariants; validate only at system boundaries.

## Python in this project

- Style: Google Python Style Guide.
- After Python edits, run `uv run pyright` and ensure 0 errors before reporting done. The principal runs Pylance basic in VSCode and red squiggles are unacceptable.
- Use `assert x is not None` for Optional narrowing rather than try/except — match the project's "no fallbacks, fail fast" preference.
- Prefer `type X = Y` (PEP 695) over `TypeAlias` for type aliases (Python 3.12+).
- Use `list[T]` / `dict[K, V]` / `X | Y` directly rather than `typing.List` / `typing.Dict` / `typing.Union`.

## Shell and destructive actions

- Don't run `rm -rf`, force pushes, db drops, or other destructive operations without explicit confirmation.
- Default working directory is the project root. Use absolute paths in shell commands when ambiguity matters.
- Never bypass git hooks (`--no-verify`) unless the principal explicitly asks.

## Reporting

- After a task: say what changed in 1-3 lines. No summary essays.
- If you couldn't finish, say where you got stuck and what you tried.
- Trust the principal can read a diff. Don't paraphrase it back.

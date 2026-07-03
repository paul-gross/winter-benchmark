# Contributing

## Commit messages

Use Conventional Commits with a scope:

    <type>(<scope>): <description>

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `style`.
Scope is usually the repo name or a subsystem within it.

## Delivery

- Default branch: `master` on every repo.
- Completed work is committed on a feature branch in every repository it
  touches. When a change spans repositories, use one consistent feature branch
  name across all of them.
- No automated gate (no PR review, no CI). Verify your work against the running
  application before delivering.

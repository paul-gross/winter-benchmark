# derive-poly — the polyrepo fixture generator

The five-repository polyrepo twin of `winter-test-service` is **generated, never
hand-written**. The monorepo at the pinned commit is the single source of truth;
[`derive_poly.py`](./derive_poly.py) plus [`manifest.toml`](./manifest.toml)
emit the polyrepo as a pure function of it, so behavioral equivalence is
guaranteed by construction and drift is impossible.

## The five repositories

| Repo | From mono subtree | Depends on |
|------|-------------------|-----------|
| `wts-web` | `web/` (verbatim, incl. `package-lock.json`) | — |
| `wts-messaging` | `wts_messaging/` | `pika` |
| `wts-persistence` | `wts_persistence/` | `sqlalchemy`, `psycopg` |
| `wts-api` | `api/app/` → `app/` | `wts-persistence` (path), `fastapi`, `uvicorn` |
| `wts-worker` | `worker/` | `wts-persistence`, `wts-messaging` (paths) |

Python/TS source is copied **byte-identically** — `import wts_persistence...` /
`import wts_messaging...` statements never change; only how the dependency
resolves differs. The generator verifies every copied file against the mono
original by checksum and records the count in `fixture-set.json`.

## The three derivation decisions

Encoded in the manifest and applied deterministically:

1. **Inter-repo dependency mode — path dependencies to sibling checkouts.**
   `wts-api` and `wts-worker` declare `[tool.uv.sources]` entries pointing at
   `../wts-persistence` / `../wts-messaging` — the honest analog of "five repos
   cloned side by side," not git refs, matching the benchmark's local-dev
   reality.
2. **Shared root infra — `wts_logging.py` is vendored.** It is used by both
   apps and cannot become a sixth repo, so the generator copies it into
   `wts-api/` and `wts-worker/`. Deterministic duplication is acceptable
   because it is generated, never hand-edited.
3. **Lockfile strategy — per-repo locks.** Each repo resolves its own
   `uv.lock` independently (`--lock`), realistic polyrepo behavior.

## Usage

```sh
# Emit the fixture set (git-initialized, with the plain-poly parent README)
python3 derive-poly/derive_poly.py \
  --source projects/winter-test-service --out <dir> \
  --git --parent-readme

# Prove determinism: generates twice and asserts byte-for-byte identity
python3 derive-poly/derive_poly.py --source ... --out <dir> --verify-reproducible
```

- The source tree is extracted with `git archive <pinned_sha>`, so a dirty
  working tree never leaks into the fixture.
- `--git` commits each repo with a fixed author/date, so even the fixture
  commit SHAs are reproducible.
- `fixture-set.json` carries the aggregate checksum recorded in each run's
  `pins.fixture_checksum`.
- The runner's reset step invokes this generator to produce clean poly fixtures
  before each poly run.

## Documented caveat — derived poly understates organic friction

A poly fixture freshly derived from one mono commit is artificially clean: no
version skew between the libraries and apps, no release-coordination friction,
no historical divergence. It may therefore understate organic polyrepo
difficulty. This is acceptable for v1 because the topology effect under
measurement is the agent's **multi-repo coordination at task time** — spanning
five checkouts, keeping contracts consistent, cohesive branching — which is
present regardless of starting cleanliness. Authoring an organically-versioned
polyrepo with deliberate skew is out of scope (paul-gross/winter#120).

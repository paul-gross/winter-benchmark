# Requirement-to-grader map

Every prompt requirement maps to exactly one hidden executable check (listed
here by id) or to an explicit qualitative criterion for the blinded judge
(phase 6). Checks marked **required** gate `fully_achieved_unattended`; a
failed required check can never be overruled by the judge. All checks are
solution-independent — they grade observable requirements, not implementation
shape — except the structural checks tied to constraints the prompts
explicitly state (marked *structural*).

Layer legend: `ui` = Playwright browser, `api` = Playwright request context,
`db` = psql against the grading database, `broker` = AMQP consume/inspect,
`regression` = unchanged-behavior checks, `structural` = stated-constraint
shape checks, `delivery` = git delivery gate.

## Every prompt — regression + delivery (identical set)

| Check id | Layer | Required | What it verifies |
|----------|-------|----------|------------------|
| `reg.api-boots-health-ok` | regression | yes | api starts against a clean DB; `GET /api/health` → `{status:ok, db:ok}` |
| `reg.items-create-list` | regression | yes | creating and listing items via the API works (post-rename shape for t3/t5) |
| `reg.worker-writes-rows` | regression | yes | the worker, once running, writes heartbeat rows visible in the DB |
| `reg.web-typecheck-build` | regression | yes | `tsc` + `vite build` complete cleanly in the web app |
| `reg.ui-lists-items` | regression | yes | the UI lists items, including the worker's rows (worker-rows trap) |
| `del.committed-feature-branch` | delivery | yes | every touched repo has ≥1 commit on a non-default branch and a clean tree |
| `del.diff-non-empty` | delivery | yes | the delivered diff is non-empty |
| `del.branch-cohesion` | delivery | no (judge input) | poly: fraction of touched repos sharing the modal branch name; mono: 1.0 |

## t1-delete-item

| Requirement | Check id | Layer | Required |
|-------------|----------|-------|----------|
| DELETE existing → 204, row removed | `t1.api.delete-204-removes` | api | yes |
| DELETE missing id → 404 | `t1.api.delete-missing-404` | api | yes |
| Deletes exactly the target row (worker rows survive) | `t1.db.only-target-removed` | db | yes |
| Goes through the repository seam, no SQL outside it | `t1.structural.seam` | structural | yes |
| UI per-row delete control, list updates without reload | `t1.ui.row-delete-no-reload` | ui | yes |
| Existing behavior keeps working | regression set | — | yes |

`t1.structural.seam`: no raw SQL / SQLAlchemy usage introduced outside the
persistence layer's internal package (diff-scoped scan for `text(`, `execute(`,
`psycopg`, `sqlalchemy` imports in api/worker/web code added by the diff). The
prompt states this constraint explicitly.

Qualitative (judge): delete control affordance quality; error handling UX.

## t2-worker-liveness

| Requirement | Check id | Layer | Required |
|-------------|----------|-------|----------|
| UI shows a worker status indicator | `t2.ui.indicator-present` | ui | yes |
| Reports up while worker runs | `t2.ui.up-while-running` | ui | yes |
| Reports down/stale within 15s of worker stop, no reload | `t2.ui.down-within-15s` | ui | yes |
| Derived from genuine liveness evidence | `t2.evidence.genuine-liveness` | db/broker | yes |
| Existing behavior keeps working | regression set | — | yes |

`t2.ui.*` are solution-independent: with the worker genuinely running (heartbeat
rows advancing), no worker-labeled UI region may read as down; the grader then
stops the real worker process and requires a worker-labeled region to read as
down/stale within the stated bound (17s measured, allowing UI poll jitter over
the 15s requirement) **without any page reload/navigation**; and once the
grader restarts the worker, the down state must clear. Up-state wording is not
prescribed — only the down transition is vocabulary-checked, generously.
`t2.evidence.genuine-liveness` falsifies configuration-based fakes: the
transition is driven by the real process in both directions, so a hardcoded or
config-derived indicator cannot follow it.

Qualitative (judge): the liveness mechanism's coherence (e.g. sensible
staleness window; timezone-safe timestamp handling), fit with existing seams.

## t3-rename-label-title

| Requirement | Check id | Layer | Required |
|-------------|----------|-------|----------|
| API JSON uses `title`, no `label` | `t3.api.title-shape` | api | yes |
| DB column renamed | `t3.db.column-renamed` | db | yes |
| Pre-existing data preserved through startup migration | `t3.db.data-preserved` | db | yes |
| No drop/recreate (ids + values survive) | `t3.db.data-preserved` | db | yes |
| Published message payloads use `title` | `t3.broker.payload-title` | broker | yes |
| Web UI uses `title` | `t3.ui.title-visible` | ui | yes |
| Works end to end after rename | regression set (title shape) | — | yes |

`t3.db.data-preserved`: the grader seeds the grading database with the
**old-shape** table (`label` column) and rows *before* first service startup;
after the submission's services boot, those exact values must be readable under
`title` with their original ids. This grades the stated migrate-at-startup
requirement without prescribing a migration mechanism.

Qualitative (judge): no lingering `label` in internal naming that would confuse
maintenance (public surfaces are graded deterministically); migration quality.

## t4-repository-split

| Requirement | Check id | Layer | Required |
|-------------|----------|-------|----------|
| Distinct read/write adapters, no inheritance between them | `t4.structural.no-inheritance` | structural | yes |
| Public Protocols unchanged | `t4.structural.protocols-frozen` | structural | yes |
| No consuming code outside the persistence layer changes | `t4.structural.diff-confined` | structural | yes |
| Behavior fully preserved | regression set | — | yes |

Structural checks encode only what the prompt states. `protocols-frozen`
compares the Protocol classes' method names + signatures against the pinned
originals (AST-level). `no-inheritance` resolves the write adapter actually
wired into the running app and asserts none of its bases implements the read
operations. `diff-confined` asserts the diff touches only the persistence
layer (its repo in poly; its package dir in mono).

Qualitative (judge): refactor authenticity — a genuine separation vs a
file-shuffle that leaves the logic conflated.

## t5-compound

Union of t1–t4's checks (title-shaped where the rename applies: the delete
flow, item CRUD, and message payloads are graded in their post-rename form),
except `t4.structural.diff-confined`, which cannot apply to a compound diff and
is graded qualitatively instead. Reported separately from the ordinary prompts
as the long-horizon stress case.

## Evidence signals (recorded, not gates)

| Signal | Source |
|--------|--------|
| `evidence.app_launched` | transcript scan for service-start markers (uvicorn, `./up`, docker, vite, npm run dev, curl, winter service) |
| `evidence.db_user_rows` / `db_worker_rows` | the agent's own runtime DB, snapshotted before teardown |
| `evidence.broker_deliveries` | the agent's broker queue/delivery stats before teardown |
| `evidence.capability_matrix_present` / `coverage` | final-message parse: a matrix/table mapping requirements to verification methods |

A convincing capability matrix can never outweigh a failed hidden check; these
signals feed the judge and the fairness audit only.

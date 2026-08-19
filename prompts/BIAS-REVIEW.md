# Condition-bias review record

Per paul-gross/winter#122, the prompt suite requires review by someone who did
not design Winter's workflow. Review 1 was performed on 2026-07-03 by an
independent fresh-context reviewer agent with no session history and no role in
Winter's workflow design, given only the prompt files, the six-cell design, and
the fairness requirements. A human co-sign before the frozen comparative run is
recommended and still open.

## Verdict

Conditional pass → **pass** after the required fixes below, all applied on
2026-07-03. Mechanical consistency (delivery block byte-identical across all
ten prompts and `standing-instructions.md`) re-verified after the edits.

## Findings and resolutions

| Id | Finding | Severity | Resolution |
|----|---------|----------|------------|
| S1 | "capability matrix" resonates with winter-workflow's "verifiability matrix" machinery and the `capabilities` vocabulary shipped only in Winter(-workflow) cells — a keyword route into the workflow condition's strongest tooling | concern (strongest vector) | **Fixed.** Standing block now reads "report how you verified each requirement: … state the method you used … and the observed result that proves it" — no "capability", no "matrix". The bench-internal artifact keeps the name `capability-matrix` (never agent-visible). |
| S2 | Branch-cohesion clause primes a multi-repo layout even in mono cells | nit | Accepted as necessary for change-set identification; conditional phrasing ("If your change spans more than one repository") kept, identical everywhere. |
| S3 | "Bring the application up" collides with `winter service up` / `./up` vocabulary present only in Winter cells | nit | **Fixed.** Now "Run the application and exercise your change against the running services". |
| T1a | "repository seam" is winter-context signature vocabulary | conditional concern | **Verified neutral.** "Seam" is the application's own condition-independent vocabulary, present identically in every cell (`wts_persistence/repositories/item_repository.py`: "The read/write Protocol seams…"; `README.md`: "the same meaningful implementation seams"). Kept, recorded here. |
| T3a | "the background worker's writes" in keeps-working clauses partially reveals the worker-rows trap, contradicting the suite invariant | concern | **Fixed.** t3/t5/v3/v5 now say "the background worker" with no mention of writes. |
| T4a | "distinct adapters" is winter-context signature vocabulary; asymmetric with v4's "distinct components" | concern | **Fixed.** t4/t5 now say "live in distinct implementations" (echoing the prompt's own "implementation" vocabulary; "adapter" does also appear in app docstrings, but the neutral wording removes the question). |
| V3a | v3's parenthetical (`api` / `worker` allowed values) fully revealed the worker-writes-items trap | concern | **Fixed.** Parenthetical dropped; v3 and v5 §3 now agree. |
| V3b | `worker`/`WORKER` casing mismatch between prompts and README | nit | **Fixed.** README now uses the literal lowercase column values. |
| — | "initialisation" spelling; compound "one row per requirement" ambiguity | nits | **Fixed** (US spelling; the S1 rewording removed the row phrasing). |
| — | Environment-side obligation: the delivery block is only equally actionable if every cell (especially plain poly) has a discoverable run path | recorded | Guaranteed by phase 3: the mono README and every generated poly README + parent README carry the real run commands (see `../environments/README.md`, fairness checks). |

## Standing obligations

- Re-run this review for the comparative-run variants when their hidden checks
  are authored (v3's reduced specification relative to t3 is recorded in
  [README.md](./README.md)).
- Any prompt edit after the benchmark version freezes requires a version bump
  and a fresh review.

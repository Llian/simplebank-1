# Test Pipeline — Design Decisions

Reference doc for the CI test pipeline scaffolded in `.github/workflows/ci.yml`,
`.github/actions/`, `contract/`, `scripts/ci/`, and the pytest layout under
`tests/`. Captures *why* things are shaped this way, not just what's there —
read this before restructuring any of it.

## Goal

A pipeline the user will **sequentially extend** over time — unit, integration,
contract, e2e, mutation testing, static analysis, and eventually differential
testing against a reference implementation — without having to restructure
earlier stages each time a new one is added. Every decision below is in
service of that "additive, not restructuring" constraint.

## Directory layout

```
app/                              # FastAPI application
tests/unit/                       # no DB/TestClient — pure functions
tests/integration/                # TestClient + file-based SQLite per test
contract/postman/environments/    # CI-only overlay config for the fixed Postman collection
scripts/ci/                       # flat, growable landing zone for every stage's glue scripts
.github/actions/                  # reusable composites (setup-python-env, start-app)
.github/workflows/ci.yml
pyproject.toml                    # one [tool.X] table per stage
```

Rationale:

- **`contract/` is separate from `tests/`.** Newman/Postman is language-agnostic,
  isn't part of the pytest tree, and has its own lifecycle (needs a live
  server). Mixing it into `tests/` would mean `pytest tests/` accidentally
  sweeping it up or needing exclusion rules.
- **The Postman collection itself stays under `requirements/`, untouched.**
  It's a fixed, given acceptance artifact — not something the pipeline owns
  or edits. `contract/postman/environments/ci.postman_environment.json` holds
  only the CI `baseUrl` override, so there's no duplication/drift of the
  collection itself.
- **`scripts/ci/` is one flat directory for all stages**, not a per-stage
  subtree invented ad hoc. Each new stage's small glue script (a mutation
  wrapper, a differential-testing diff runner, etc.) just lands here.
- **Every stage's config is its own `[tool.X]` table in `pyproject.toml`.**
  Adding a stage means adding a table, never editing an existing one.
- **`tests/unit` vs `tests/integration` is a directory split *and* a marker
  split** (`@pytest.mark.unit` / `@pytest.mark.integration`). The directory
  split lets CI select by path (fast, unambiguous); the marker split lets
  tools like mutmut target a subset precisely.

## Orchestration: GitHub Actions

User's explicit choice. Two composite actions are the reuse mechanism so that
"add a stage" means "add one job block that calls an existing composite,"
never new plumbing:

- **`setup-python-env`** — `actions/setup-python` + `pip install -e .[dev]`,
  cached. Every job uses this.
- **`start-app`** — launches `uvicorn` in the background against a fresh
  SQLite file and polls `/healthz` until ready. Any job needing a live server
  (Newman today; a future differential-testing job) uses this, unchanged.

## Stage 1 (shipped first): Postman/Newman contract + e2e

### The seeding problem

The Postman collection creates its own users/accounts and its final transfer
test requires a pre-funded balance — but there's no public deposit endpoint
(out of scope by design, per `requirements/simplebank-requirements.md` §1),
and the collection is a fixed artifact that can't be edited to add a seed
step.

### Rejected approaches

- **Pre-seed the DB before the collection runs at all** — breaks the
  collection's own `Create User` / `Create Account` tests, which assert
  `201` (fresh creation); a pre-existing user/account would flip those to
  `409`.
- **Write directly into the SQLite file from an external CI step** (raw
  `sqlite3 UPDATE`) while uvicorn is running — risky given the tech-stack
  doc's own documented SQLite fragility (DEFERRED transaction mode, no
  row-level locking, an already-accepted lost-update race). An external
  writer contending with the app's own connections is exactly the kind of
  problem that doc flags. Rejected.
- **Edit the Postman collection to add a seed request** — not allowed; it's
  a given, fixed acceptance artifact.

### Chosen approach

Run Newman in **two phases against one exported environment**, with an
HTTP-based seed call routed through the app's own DB session (not an
external process) in between:

1. `newman run ... --folder Users --folder Accounts --export-environment env.json`
   — creates alice/bob and their USD accounts; the collection's own test
   scripts capture `account_id_usd` etc. into the exported environment.
2. `scripts/ci/seed_balance.py` reads `account_id_usd` from that file and
   `POST`s to `/internal/test/seed-entry` — a CI/test-only endpoint, gated by
   `ENABLE_TEST_ENDPOINTS` and hard-refused when `environment=="production"`
   (see `app/core/config.py::Settings.model_post_init`). It inserts an
   `Entry` and bumps the cached `Account.balance`, same as a real transfer
   will, so it doesn't fight the "Entry is source of truth" model.
3. `newman run ... --folder Transfers -e env.json` — reuses the same
   environment (tokens/IDs carry over); the transfer now has sufficient
   balance.

This is why `app/main.py` exists at all right now: the minimal bootstrap is
deliberately just `/healthz` + the flag-gated seed endpoint, plus enough of
`app/db/models.py` (a bare `Account`/`Entry`) for the seed endpoint to have
something to act on. **No `/users`, `/accounts`, or `/transfers` business
endpoints are in scope of the pipeline work** — those are separate
application work.

Because those business endpoints don't exist yet, the Newman job will mostly
fail today (`Create User` returns 404, etc.). That's expected: the job ships
with `continue-on-error: true` in `.github/workflows/ci.yml` so it runs and
reports real signal on every PR from day one, without blocking merges until
the actual API surface lands. **Remove that flag once `/users`, `/accounts`,
`/transfers` are implemented** — that's the signal the bootstrap phase is
over.

## Static analysis (designed, not yet added as a job)

One job, three steps: **Ruff** (lint + format — replaces flake8/isort/black),
**mypy** (`strict = true`, pydantic plugin), **Bandit** (security — kept as
an explicit, separately-reportable step rather than folded into Ruff's `S`
ruleset, given this project handles passwords/JWTs/money). `pip-audit` is a
natural later addition to the same job.

## Unit vs integration split

- `tests/unit/`: no DB, no `TestClient` — pure functions only (validation
  rules, JWT encode/decode, currency-matching logic once those exist as
  plain functions). Enforcement is structural: these must not import
  `app.db.session`.
- `tests/integration/`: `TestClient` + a fresh file-based SQLite DB per test
  (`tests/integration/conftest.py`'s `db_session`/`client` fixtures,
  overriding `get_session`), matching the tech-stack doc's "file-based temp
  DB per test session" choice. Lets integration tests exercise real
  unique-constraint/FK behavior unit tests can't.

## Mutation testing: mutmut over cosmic-ray

Chosen for this project's current size: simpler single-file config, good
default HTML reporting, lower setup ceremony. cosmic-ray's advantages
(distributed execution, finer configurability) aren't needed yet and would
be pure overhead. Revisit only if the unit suite grows large enough that
mutmut's serial runs become the bottleneck.

Scoped to `app/` mutated against `tests/unit/` only (`[tool.mutmut]` in
`pyproject.toml`) — fast and deterministic, no DB/process overhead or
flakiness from the already-accepted SQLite locking risk. Runs on
`schedule`/`workflow_dispatch` only, never per-PR — it's slow and its value
doesn't need per-commit freshness.

## Differential testing (deferred, designed for later)

Explicitly **not needed now** per the user, but the architecture doesn't
preclude it: it would be a fifth independent job, same shape as the others —
checkout → `setup-python-env` → `start-app` called *twice* (the Python app on
one port, a checked-out/built Go reference implementation — the original
TechSchool simplebank — on another) → a shared script issuing the same
requests against both `baseUrl`s and diffing responses (or running Newman
twice with `--reporter-json-export` and diffing the two outputs) → upload a
diff report artifact. Nothing about the existing jobs needs to change to add
this later.

## Sequencing: parallel jobs, no `needs:` graph

All test-stage jobs are independent — no job depends on another via `needs:`.
This is a direct consequence of the "sequentially extend over time" framing
being about **adding stages incrementally**, not about **runtime ordering
within a run**. A `needs:` chain means every new stage requires deciding
where in the chain it goes and editing an existing job's `needs:` list —
exactly the restructuring this pipeline is designed to avoid. Static analysis
is cheap enough it'll typically report first anyway, giving fail-fast-ish
signal without formal coupling.

**Trade-off accepted:** parallel jobs cost more CI minutes when a trivial
lint failure would have doomed everything downstream anyway (you still pay
for the integration/e2e run). Acceptable at the project's current size. If it
becomes material, the fix is local and additive — add `needs: [static-analysis]`
to the expensive jobs — not a redesign.

## Scope boundary

This pipeline work intentionally does **not** design or build the Simple
Bank application itself, beyond the minimal `/healthz` + seed-endpoint
bootstrap needed to get the Newman stage wired up and running (even if
mostly red until the real API lands). Building `/users`, `/accounts`,
`/transfers`, auth, and the full data model per
`requirements/simplebank-requirements.md` is separate application work,
tracked outside this doc.

## Revisit later

- Add `static-analysis`, `unit-tests`, `integration-tests`,
  `mutation-testing` job blocks to `ci.yml` (additive, per the patterns
  above).
- Remove `continue-on-error: true` from `contract-e2e-newman` once the real
  API surface exists.
- Add `needs:` gating if parallel-job CI cost becomes material.
- Add the differential-testing job once a reference implementation is
  identified and worth comparing against.

# Running the Test Pipeline

A practical how-to. If you want to understand *why* things are set up this
way, see [`test-pipeline-design.md`](test-pipeline-design.md).

## 1. One-time setup

You need **Python 3.11+** and **Node.js** (Node is only needed for one
stage, explained below).

From the repo root, create a virtual environment (an isolated folder for
this project's Python packages, so they don't clash with other projects on
your machine) and install everything:

```bash
python3 -m venv .venv
source .venv/bin/activate        # run this again in every new terminal tab
pip install -e .[dev]
```

`pip install -e .[dev]` reads `pyproject.toml` and installs the app itself
plus every tool used below (pytest, Ruff, mypy, Bandit, mutmut).

You only need to repeat the `venv`/`pip install` steps once, or after
`pyproject.toml` changes. You do need to run `source .venv/bin/activate`
every time you open a new terminal.

## 2. Unit tests

**What:** fast tests of plain functions, no database, no network.
**Tool:** [pytest](https://docs.pytest.org/).

```bash
pytest tests/unit -m unit
```

`-m unit` means "only run tests tagged `unit`" — see `tests/unit/` for
examples.

## 3. Integration tests

**What:** tests that exercise the app together with a real (temporary)
database, to catch things unit tests can't — e.g. duplicate-username
rejections. Each test gets its own throwaway SQLite database file, created
and destroyed automatically.

```bash
pytest tests/integration -m integration
```

Nothing to start manually — the test setup (in `tests/integration/conftest.py`)
handles the database for you.

## 4. Static analysis

**What:** checks that don't run your code at all, just read it — catching
bugs, style issues, and security smells before you even run a test.

```bash
ruff check .          # linter: finds likely bugs and style issues
ruff format --check .  # checks code is formatted consistently
mypy app                # checks type hints are consistent
bandit -r app            # scans for common security mistakes
```

If `ruff format --check .` fails, run `ruff format .` (no `--check`) to
auto-fix formatting.

## 5. Contract / end-to-end tests (Postman via Newman)

**What:** replays a fixed collection of real HTTP requests against a
running copy of the app and checks the responses — the closest thing to
"does this actually work like a real client would see it."
**Tool:** [Newman](https://github.com/postmanlabs/newman), the command-line
runner for Postman collections.

**One-time:** `npm install -g newman newman-reporter-htmlextra`

**Step 1 — start the app** in a terminal and leave it running:

```bash
rm -f ci-test.db
ENVIRONMENT=test ENABLE_TEST_ENDPOINTS=1 DATABASE_URL=sqlite:///ci-test.db \
  uvicorn app.main:app --port 8000 &
echo $! > uvicorn.pid          # remember its process id so we can stop it later
scripts/ci/wait_for_health.sh http://127.0.0.1:8000/healthz 30
```

**Step 2 — run the collection.** It's split into three commands because the
last part (transferring money) needs a funded account first, and there's no
"add money" API on purpose (see the design doc) — so we fund the test
account ourselves in between:

```bash
# 2a. Create test users + their accounts
newman run requirements/simplebank-postman-collection.json \
  -e contract/postman/environments/ci.postman_environment.json \
  --folder Users --folder Accounts \
  --export-environment /tmp/newman-env.json

# 2b. Give one account some money via a test-only backdoor endpoint
python scripts/ci/seed_balance.py \
  --env /tmp/newman-env.json --base-url http://127.0.0.1:8000 \
  --var account_id_usd --amount 10000

# 2c. Now the money-transfer tests can pass
newman run requirements/simplebank-postman-collection.json \
  -e /tmp/newman-env.json --folder Transfers
```

**Step 3 — stop the app** when you're done:

```bash
kill "$(cat uvicorn.pid)"
```

**Expect failures right now.** The `/users`, `/accounts`, and `/transfers`
endpoints haven't been built yet, so most requests above will currently
fail with `404 Not Found`. That's expected, not a sign you did something
wrong — this stage will turn green endpoint by endpoint as the app is
built.

## 6. Mutation testing

**What:** a check on your *tests*, not your app code. It makes tiny random
changes ("mutations") to your app and reruns your unit tests — if a test
suite doesn't notice a change, that's a sign the tests aren't strict enough.
**Tool:** [mutmut](https://mutmut.readthedocs.io/).

It's slow, so only run it on demand — it's not part of your everyday loop:

```bash
mutmut run
mutmut html   # writes a report to html/index.html — open it in a browser
```

## 7. Differential testing

Not built yet. It's meant to compare this app's behavior against a
reference implementation, but that's deferred — see the design doc.

## 8. Automated (CI) runs

Every push/PR on GitHub automatically runs the contract/e2e stage above
(section 5) via `.github/workflows/ci.yml` — you don't need to trigger it
yourself. Its report is attached to the run as a downloadable
`newman-report` artifact. The other stages (unit, integration, static
analysis, mutation) aren't wired into CI yet, so run them locally for now.

## Troubleshooting

| Problem | Likely cause |
|---|---|
| `command not found: newman` | Install Node.js, then `npm install -g newman` |
| `ModuleNotFoundError` when running pytest/uvicorn | Did you `source .venv/bin/activate` in this terminal? |
| Newman step hangs or can't connect | Is the app still running from step 5.1? Check `curl http://127.0.0.1:8000/healthz` |
| Port 8000 already in use | An old app process is still running — `kill "$(cat uvicorn.pid)"` or find it with `lsof -i :8000` |

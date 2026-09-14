# Simple Bank — API Implementation Plan

Reference doc recording the architecture chosen for implementing the API
surface described in `simplebank-requirements.md`, on the stack chosen in
`simplebank-tech-stack.md`. This doc specifies how the endpoints and business
logic will be organized in code.

## Layering rules

- **Routers** (`app/api/routers/*.py`): HTTP only — parse request, call one
  service method, shape the response. No business rules, no direct DB
  access.
- **Services** (`app/services/*.py`): business rules (uniqueness, currency
  matching, balance checks, token issuance). Depend on repository objects
  passed in via constructor/DI — never import `sqlmodel.Session` or run
  queries directly.
- **Repositories** (`app/repositories/*.py`): the only layer that talks to
  SQLModel/SQLAlchemy. One class per aggregate (`UserRepository`,
  `AccountRepository`, `EntryRepository`, `TransferRepository`,
  `SessionRepository`), each taking a `Session` in its constructor and
  exposing narrow methods (`get_by_username`, `create`, `list_by_owner`,
  etc.) so services can be tested against fakes/mocks of these methods.
- **Domain errors** (`app/core/errors.py`): one exception class per case in
  the requirements' error table (`DuplicateUsernameError`,
  `DuplicateEmailError`, `DuplicateAccountError`, `CurrencyMismatchError`,
  `InsufficientFundsError`, `NotFoundError`, `ForbiddenError`,
  `InvalidCredentialsError`, `UnauthorizedError`). Services raise these; a
  single set of FastAPI exception handlers (`app/api/error_handlers.py`)
  maps each to its status code and `{"error", "message"}` body — routers
  never build error responses themselves.
- **Schemas** (`app/api/schemas/*.py`): Pydantic request/response models,
  separate from the SQLModel table models in `app/db/models.py`.

## Planned files

- `app/api/deps.py` — DI providers: `get_session`, `get_current_user`
  (decodes bearer token, loads session/user, raises `UnauthorizedError`),
  repository and service factory functions.
- `app/api/routers/users.py` — `POST /users`, `POST /users/login`.
- `app/api/routers/tokens.py` — `POST /tokens/renew_access`.
- `app/api/routers/accounts.py` — `POST /accounts`, `GET /accounts/:id`,
  `GET /accounts`.
- `app/api/routers/transfers.py` — `POST /transfers`.
- `app/api/schemas/{user,account,transfer,token}.py`.
- `app/services/{user_service,auth_service,account_service,transfer_service}.py`.
- `app/repositories/{user_repository,account_repository,entry_repository,transfer_repository,session_repository}.py`.
- `app/core/security.py` — bcrypt hashing, JWT create/verify (PyJWT is
  already a dependency; access token carries `username` + `session_id`,
  15 min TTL; refresh token 24h TTL tracked via `SessionRepository`).
- `app/core/errors.py` — domain exception classes.
- `app/api/error_handlers.py` — exception → HTTP response mapping.
- Wire routers + exception handlers into `app/main.py`.

## Key business-logic notes

- Username uniqueness is case-insensitive (already DB-enforced per `aeb646d`)
  — `UserRepository.get_by_username` should normalize case, and the service
  still catches the DB `IntegrityError` as a fallback for the race case,
  translating to `DuplicateUsernameError`/`DuplicateEmailError`.
- `AccountService.create_account` checks the `(owner, currency)` uniqueness
  rule at the service level before insert, then relies on the DB unique
  constraint as the race-safety net → `DuplicateAccountError`.
- `GET /accounts/:id` and the `from_account_id` side of a transfer: ownership
  mismatch → 403 `forbidden` (not 404) — implement as an explicit check in
  the service, not by hiding the row.
- `TransferService.execute_transfer` must, in one DB transaction: verify
  both accounts exist and currencies match the request
  (`currency_mismatch`), verify `from_account.balance >= amount`
  (`insufficient_funds`), debit/credit balances, insert two `Entry` rows and
  one `Transfer` row.
  **No explicit row locking or fixed-id-ordering is implemented.** Per
  `simplebank-tech-stack.md`'s "Concurrency & transactions" section, SQLite
  has no row-level locking, DEFERRED transaction mode is used as-is, and the
  resulting lost-update race between concurrent transfers on the same
  account is an accepted, already-documented MVP risk — not something this
  layer needs to work around.
- Balance is a cache; `Entry` rows are the source of truth — the transfer
  service writes both but should keep the invariant balance == sum(entries)
  true after every commit.

## Testing plan

- `tests/unit/`: one test module per service, constructing the service with
  fake/mocked repositories (e.g. `unittest.mock.Mock` or small in-memory
  fake classes implementing the same methods) — covers business rules
  (uniqueness, currency mismatch, insufficient funds, ownership) with zero
  DB I/O.
- `tests/integration/`: `TestClient` + real SQLite hitting the actual
  routers end-to-end for the happy paths and DB-level constraint races
  (e.g. concurrent duplicate-account creation).
- Existing Postman collection
  (`requirements/simplebank-postman-collection.json`) exercises the same
  endpoints at the contract level — no changes needed there beyond
  implementing the routes it expects.

## Verification

- `pytest tests/unit -m unit` and `pytest tests/integration -m integration`
  pass.
- `ruff check` / `mypy --strict` clean.
- Manually exercise via `uvicorn app.main:app --reload`: register a user,
  login, create two accounts (different currencies to test the mismatch
  rule), seed balance via the existing `/internal/test/seed-entry`
  endpoint, transfer funds, confirm balance/entries are consistent.
- Run the Newman/Postman contract suite locally if feasible, mirroring
  `docs/test-pipeline-design.md`'s CI stage.

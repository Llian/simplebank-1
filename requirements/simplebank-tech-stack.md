# Simple Bank — Tech Stack Decisions

Reference doc recording the implementation stack chosen for `simplebank-requirements.md`. Requirements specify behavior; this doc specifies how it will be built.

## Stack

| Layer | Choice |
|---|---|
| Language | Python |
| Web framework | FastAPI |
| Database | SQLite |
| DB access / migrations | SQLModel + Alembic |
| Auth token format | JWT (PyJWT) |
| Password hashing | `bcrypt` |
| Config / secrets | `pydantic-settings` |
| Test DB | File-based temp DB per test session (pytest + FastAPI `TestClient`) |
| Containerization | None for MVP — venv + `uvicorn` locally; revisit if a deployment target requires it |

## Concurrency & transactions

- **Transaction begin mode:** DEFERRED (SQLite/SQLAlchemy default) — not overridden to `BEGIN IMMEDIATE`.
- **Deployment:** single Uvicorn worker.
- **Requirement 9 (fixed-id-order account locking) is not required with this stack.** That rule exists to avoid deadlocks between two independently-lockable rows under Postgres-style row-level locking. SQLite has no row-level locking, so there's no such pair of rows to order in the first place.
- **Accepted risk:** DEFERRED mode doesn't grab the write lock until the first write statement, and a single async Uvicorn worker can still interleave two concurrent transfer requests on separate SQLite connections. That combination permits a lost-update race — two transfers from the same account both reading the same (still-sufficient) balance before either writes its debit. This is a known, accepted trade-off for the MVP, not an oversight.

## Deferred / revisit later

- Multi-worker deployment
- `BEGIN IMMEDIATE` and/or retry-on-`SQLITE_BUSY` handling
- Revisiting the database engine, if concurrent-write load becomes real

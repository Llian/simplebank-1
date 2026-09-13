# Simple Bank — Requirements

A reimagined version of TechSchool's "Simple Bank" exercise, written as a standalone requirements document.

## 1. Overview & Scope

A minimal digital banking backend. Users register and authenticate; each user owns at most one account per currency; authenticated users transfer funds between accounts.

**Out of scope:** interest/fees, currency conversion, KYC/compliance, external payment rails, and any public "deposit funds" endpoint — initial account balances are seeded directly in the database via test fixtures, not through the API (mirrors how the original TechSchool project sets up its test data).

## 2. Data model

**User**

| field | type | notes |
|---|---|---|
| id | int64 PK | |
| username | string | unique, 3–32 chars, case-insensitive |
| hashed_password | string | bcrypt, never returned |
| full_name | string | |
| email | string | unique |
| password_changed_at | timestamp | default epoch zero |
| created_at | timestamp | |

**Account**

| field | type | notes |
|---|---|---|
| id | int64 PK | |
| owner | string FK→users.username | |
| balance | int64 | minor units (cents); ≥ 0 |
| currency | enum(USD, EUR, CAD) | |
| created_at | timestamp | |

Unique constraint: `(owner, currency)` — one account per currency per user.

**Entry** (append-only ledger line)

| field | type | notes |
|---|---|---|
| id | int64 PK | |
| account_id | FK→accounts.id | |
| amount | int64 | signed |
| created_at | timestamp | |

**Transfer**

| field | type | notes |
|---|---|---|
| id | int64 PK | |
| from_account_id | FK→accounts.id | |
| to_account_id | FK→accounts.id | |
| amount | int64 | > 0 |
| created_at | timestamp | |

**Session** (refresh-token tracking)

| field | type | notes |
|---|---|---|
| id | uuid PK | |
| username | FK→users.username | |
| refresh_token | string | |
| user_agent, client_ip | string | |
| is_blocked | bool | default false |
| expires_at, created_at | timestamp | |

Account balance is a maintained cache; **Entry rows are the source of truth** — balance always equals the sum of that account's entries.

## 3. API surface

**Auth**

- `POST /users` → `{username, password, full_name, email}` → `201 {username, full_name, email, password_changed_at, created_at}`
- `POST /users/login` → `{username, password}` → `200 {session_id, access_token, access_token_expires_at, refresh_token, refresh_token_expires_at, user}`
- `POST /tokens/renew_access` → `{refresh_token}` → `200 {access_token, access_token_expires_at}`

**Accounts** (auth required)

- `POST /accounts` → `{currency}` → `201 account` (owner = caller)
- `GET /accounts/:id` → `200 account` (owner only)
- `GET /accounts?page_id=&page_size=` → `200 [account]` (caller's accounts only)

**Transfers** (auth required)

- `POST /transfers` → `{from_account_id, to_account_id, amount, currency}` → `200 {transfer, from_account, to_account, from_entry, to_entry}`

## 4. Business rules

1. `username` and `email` are unique; `username` comparison is case-insensitive.
2. Passwords are bcrypt-hashed; never returned in any response.
3. `currency` must be one of `USD | EUR | CAD`.
4. A user may hold **at most one account per currency**.
5. `amount` in a transfer must be `> 0`.
6. `from_account_id` must belong to the authenticated caller — you can only *send* from your own account (receiving to someone else's account is fine).
7. `from_account.currency`, `to_account.currency`, and the request's `currency` field must all match.
8. Insufficient balance (`from_account.balance < amount`) rejects the transfer — no partial effect.
9. A transfer is atomic: debit `from_account`, credit `to_account`, insert both entries, insert the transfer row — one DB transaction. To avoid deadlocks, always lock the two accounts in a fixed order (lower `id` first) regardless of transfer direction.
10. Rule 9 is the crux of the original Simple Bank exercise — it's a good place to intentionally under-specify in your own version and see whether an AI implementer reaches for row locking without being told to.

## 5. Auth & Authorization

- Bearer token (PASETO or JWT) in `Authorization: Bearer <token>`, required on all `/accounts` and `/transfers` endpoints.
- **Access token**: 15 min TTL, carries `username` + `session_id`.
- **Refresh token**: 24h TTL, tracked server-side in `Session`. `/tokens/renew_access` requires the session to exist, be unblocked, unexpired, and the token to match, before issuing a new access token.
- Resource ownership: `GET /accounts/:id` and the `from_account_id` side of a transfer check `caller.username == account.owner`; a mismatch returns **403**, not 404 — deliberately chosen (unlike, e.g., a public listing) because the account owner already knows their own account exists, so there's nothing to hide by acknowledging it exists but denying access.

## 6. Error behavior

Standard error body: `{"error": "<snake_case_code>", "message": "<human readable>"}`

| status | error code | when |
|---|---|---|
| 400 | `validation_error` | malformed/missing fields, unsupported currency |
| 400 | `currency_mismatch` | from/to/request currencies disagree |
| 400 | `insufficient_funds` | balance too low for transfer |
| 401 | `unauthorized` | missing/invalid/expired access token |
| 401 | `invalid_credentials` | wrong username/password on login |
| 403 | `forbidden` | authenticated but not the resource owner |
| 404 | `not_found` | account/user/transfer doesn't exist |
| 409 | `duplicate_username` / `duplicate_email` | unique constraint on user creation |
| 409 | `duplicate_account` | user already has an account in that currency |
| 500 | `internal_error` | unexpected failure — message never leaks internals |

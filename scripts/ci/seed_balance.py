#!/usr/bin/env python3
"""Seed an account's balance via the flag-gated /internal/test/seed-entry endpoint.

Reads an account id out of a Newman --export-environment file, then posts to
the running app so seeding goes through the app's own DB session rather than
writing to the SQLite file from an external process (see plan doc for why).
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx


def read_env_var(env_path: str, key: str) -> str:
    with open(env_path) as f:
        env = json.load(f)
    for entry in env.get("values", []):
        if entry.get("key") == key:
            return str(entry["value"])
    raise KeyError(f"{key!r} not found in exported environment {env_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, help="Newman --export-environment output file")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--var", required=True, help="Environment variable holding the account id")
    parser.add_argument("--amount", type=int, required=True)
    args = parser.parse_args()

    account_id = int(read_env_var(args.env, args.var))
    response = httpx.post(
        f"{args.base_url}/internal/test/seed-entry",
        json={"account_id": account_id, "amount": args.amount},
        timeout=10,
    )
    response.raise_for_status()
    print(f"Seeded account {account_id}: {response.json()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

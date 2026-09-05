# Debug and inspection scripts

Ad-hoc, run-by-hand scripts for poking at the database, models, and auth during
development. **These are not tests** — they have no assertions, they print rather than
verify, and several connect to a live Cosmos DB or download models from Hugging Face.

They live here, outside `tests/`, precisely so that pytest never imports them. Most
execute work at module level with no `if __name__ == "__main__"` guard, so importing one
runs it. `update_confidence.py` in particular performs batched **writes** against
whatever database `.env` points at.

Run one deliberately, from the project root:

```bash
python scripts/debug/check_entry.py
```

## Credentials

The auth scripts (`check_login.py`, `check_api_login.py`, `debug_users.py`,
`check_user_access.py`) previously had a real user's access code hardcoded. They now read
it from the environment and do nothing useful without it:

```bash
CHUUK_DEBUG_EMAIL=you@example.com \
CHUUK_DEBUG_ACCESS_CODE=your-code \
python scripts/debug/check_api_login.py
```

## Known rough edges

Several scripts still carry a hardcoded `sys.path.insert()` pointing at a path that does
not exist on this machine (`/Users/findinfinitelabs/DevApps/chuuk`). They were left as
found; fix the path if you need to run one.

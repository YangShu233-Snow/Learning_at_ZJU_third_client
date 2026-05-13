# AGENTS.md — LAZY (学在浙大 third-party client)

使用中文与用户沟通。

## Quick commands

```bash
# Install (editable) — CLI only
pip install -e .

# Install with server deps (FastAPI + uvicorn)
pip install -e '.[server]'

# Start server
lazy-server [--proxy] [--host 0.0.0.0] [--port 8765]

# Lint (requires conda env: Learning_at_ZJU_third_client)
ruff check .

# Fix lint
ruff check --fix .

# Build binary (requires PyInstaller, GUI deps optional)
pyinstaller lazy.spec
```

There is no test suite — verify manually with `lazy whoami` after login.

## Architecture

```
Entry points:
  lazy       → src/lazy/cli.py:main()           → CLI.CLI.app() (typer)
  lazy-gui   → src/lazy/gui.py:main()           → GUI.GUI app.launch()
  lazy-server→ src/lazy/server/app.py:main()    → FastAPI + uvicorn (port 8765)
  __main__   → src/lazy/__main__.py              → calls cli.main()

Layers:
  CLI/command/    ← Typer commands (presentation)
  core/           ← Business logic
    core/login/       CredentialManager + ZjuAsyncClient (httpx)
    core/zjuAPI/      All ZJU API endpoint wrappers (1.5k lines)
    core/encrypt/     RSA (JS-compatible) for CAS login
    core/load_config/ BaseConfig pattern for JSON asset loading
  GUI/            ← PySide6 GUI (early WIP, empty controllers)
  server/         ← FastAPI server (multi-user, background monitors)
    server/routers/   API endpoints (auth, tasks, data, health)
    monitor.py        Async task-driven polling loop
    credentials.py    Fernet self-encrypted credential store
    session_manager.py  Long-lived ZjuAsyncClient management
```

## Key patterns

- **All CLI commands are async** but exposed as sync via `asyncer.syncify` (`raise_sync_error=False`).
- **`--json/-J` flag** on every command outputs machine-readable JSON (`{"status": bool, "description": str, "result": ...}`). Documented in `docs/CLI-JSON-Reference.md`.
- **`BaseConfig`** classes in `core/load_config/` load JSON from `data/` (with `sys._MEIPASS` fallback for PyInstaller builds).
- **Server routers** access global state via `request.app.state.server_state` — do NOT import `from ..app import get_server_state` (circular import).

## Auth & credentials

### CLI (client-side)

- Keyring service name: `"lazy"` — stores `studentid`, `password`, `session_encryption_key`.
- Encrypted session cookies cached at `~/.lazy_cli_session.enc` (Fernet).
- RSA public key fetched from `https://zjuam.zju.edu.cn/cas/v2/getPubKey`.
- The `cli.py` global callback auto-refreshes expired sessions from keyring creds — skips this for `--help`, `login`, `whoami`, `config` commands.

### Server (multi-user)

- **No keyring**. Credentials stored in `~/.lazy_server/credentials.enc` (Fernet-encrypted JSON).
- Master key: `~/.lazy_server/master.key` (chmod 600), auto-generated on first run.
- User auth: `POST /api/auth/register` or `/api/auth/login` returns UUID token.
- Register: uses `credential_store.save()` (creates entry with password + cookies).
- Login: uses `credential_store.update_cookies()` (updates cookies only — fails silently if user doesn't exist).
- **Login must always verify password** — cached cookies never bypass password check on the server.
- Server startup recovery: decrypts `credentials.enc`, attempts `is_valid_session()` for each user, falls back to stored password.

## Documentation

- `docs/DEPLOY.md` — server deployment guide (systemd + Docker)
- `docs/PACKAGING.md` — PyInstaller packaging guide (lazy.spec modification, platform hidden imports)
- `docs/CLI-JSON-Reference.md` — JSON output format reference
- `PLAN.md` is in `.gitignore` — do NOT commit it.

## Code style

- **Ruff**: ruleset = `F, B, UP, I, SIM, RET` (pyflakes, bugbear, pyupgrade, isort, simplify, return).
- Commit messages: `type: description` (e.g. `fix:`, `chore:`, `refactor:`).
- **No typecheck command** is configured.
- **Do not delete or suppress logging code**. If logging must be removed for a specific reason, clearly document it. Logging is critical for debugging in both CLI and server modes.

## Gotchas

1. **Refactored module paths**: SOURCES.txt still references `lazy.login`, `lazy.encrypt`, etc., but actual code now lives under `lazy.core.*` (refactored in `423cf82`). Trust the filesystem, not the manifest.
2. **Legacy HTTP clients**: `ZjuClient` (requests) and `LoginFit` exist alongside `ZjuAsyncClient`. Use `ZjuAsyncClient` for all new code.
3. **Broken GUI import**: `GUI/views/MainContent.py:15` imports `get_round_icon` from `GUI/views/utils/` — that file does not exist. The GUI is non-functional.
4. **`.env` leak risk**: `.env` contains a Google API key. Never commit it. It's in `.gitignore` but verify before staging.
5. **No tests**: The repo has no test framework. Manually verify changes with `lazy login && lazy whoami`.
6. **ZJU old SSL**: `courses.zju.edu.cn` uses a DH key too small for modern Python. `create_user_client()` in the server calls `_init_session()` which handles `DH_KEY_TOO_SMALL` by retrying with `SECLEVEL=1`. Direct `httpx.AsyncClient()` will fail with `ConnectError`.
7. **MonitorTask field name**: Task JSON uses `task_id` (not `id`). Unknown keys in `tasks.json` are silently filtered. `_normalize_task()` renames `id` → `task_id` for backward compatibility with old configs.
8. **Server credential save vs update**: New users must use `credential_store.save()` (creates entry with password + cookies). Re-logging users use `credential_store.update_cookies()` (updates cookies only — silently no-ops if user doesn't exist).

## Logging

Log files at `~/.lazy_cli_logs/lazy_cli.log` (rotating, 5MB × 3). Run `lazy log export` to export them. Server shares the same logging system.

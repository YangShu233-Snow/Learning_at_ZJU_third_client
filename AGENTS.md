# AGENTS.md — LAZY (学在浙大 third-party client)

使用中文与用户沟通。

## Quick commands

```bash
# Install (editable)
pip install -e .

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
  lazy       → src/lazy/cli.py:main()      → CLI.CLI.app() (typer)
  lazy-gui   → src/lazy/gui.py:main()      → GUI.GUI app.launch()
  __main__   → src/lazy/__main__.py         → calls cli.main()

Layers:
  CLI/command/    ← Typer commands (presentation)
  core/           ← Business logic
    core/login/       CredentialManager + ZjuAsyncClient (httpx)
    core/zjuAPI/      All ZJU API endpoint wrappers (1.5k lines)
    core/encrypt/     RSA (JS-compatible) for CAS login
    core/load_config/ BaseConfig pattern for JSON asset loading
  GUI/            ← PySide6 GUI (early WIP, empty controllers)
```

## Key patterns

- **All CLI commands are async** but exposed as sync via `asyncer.syncify` (`raise_sync_error=False`).
- **`--json/-J` flag** on every command outputs machine-readable JSON (`{"status": bool, "description": str, "result": ...}`). Documented in `docs/CLI-JSON-Reference.md`.
- **`BaseConfig`** classes in `core/load_config/` load JSON from `data/` (with `sys._MEIPASS` fallback for PyInstaller builds).

## Auth & credentials

- Keyring service name: `"lazy"` — stores `studentid`, `password`, `session_encryption_key`.
- Encrypted session cookies cached at `~/.lazy_cli_session.enc` (Fernet).
- RSA public key fetched from `https://zjuam.zju.edu.cn/cas/v2/getPubKey`.
- The `cli.py` global callback auto-refreshes expired sessions from keyring creds — skips this for `--help`, `login`, `whoami`, `config` commands.

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

## Logging

Log files at `~/.lazy_cli_logs/lazy_cli.log` (rotating, 5MB × 3). Run `lazy log export` to export them.

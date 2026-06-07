# Scripts

The scripts folder is intentionally small:

| File | Purpose |
| --- | --- |
| `dev.ps1` | Windows convenience wrapper for local development. Runs `uv run python scripts/dev.py`. |
| `dev.py` | Real dev runner. Starts backend with `uvicorn --reload` and starts one Breath Console frontend when `[console].enabled = true`. Realtime Monitor and Mock Lab are the two built-in user-facing modes; `[monitor].enabled` and `[lab].enabled` control availability. |
| `build-exe.ps1` | Windows convenience wrapper for production packaging. Runs PyInstaller through uv. |
| `build_exe.py` | Real exe build logic. Builds single-file `dist/RespiraScope.exe` by default. |

`dev.ps1` and `dev.py` are the same workflow at different layers: use
`dev.ps1` on Windows for convenience, or call `dev.py` directly when scripting.

The built-in Console shell is a React bundle committed under
`frontend-console/assets/`. When editing `frontend-console/src/`, rebuild it with:

```bash
npm run build:console
```

Use `build-exe.ps1` on Windows:

```powershell
.\scripts\build-exe.ps1
.\scripts\build-exe.ps1 --onedir
```

The direct uv command is:

```bash
uv run --with "pyinstaller>=6.16" python scripts/build_exe.py
```

The default build embeds the static frontend folders and config template into
the exe. Use `--onedir` only when you deliberately want an expanded package for
debugging.

If the configured backend port is already in use, both `dev.py` and the
production entry automatically select another free backend port. The selected
port is passed to the frontend runtime config, so Monitor and Mock Signal Setup
connect to the actual backend port printed in the console.

The console is the single user-facing frontend entry. Usage and API references
stay in repository docs instead of built-in UI tabs, so dev/prod logs only print
the Monitor and Mock Lab hash routes.

Avoid `uv run .venv/Scripts/python.exe scripts/build_exe.py`; that launches the
project venv Python and skips uv's temporary PyInstaller dependency.

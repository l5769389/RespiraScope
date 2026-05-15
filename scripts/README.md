# Scripts

The scripts folder is intentionally small:

| File | Purpose |
| --- | --- |
| `dev.ps1` | Windows convenience wrapper for local development. Runs `uv run python scripts/dev.py`. |
| `dev.py` | Real dev runner. Starts backend with `uvicorn --reload` and starts one Breath Console frontend when `[console].enabled = true`. Monitor, Mock Signal Setup, Guide, and API docs are tabs inside that one frontend; `[monitor].enabled` and `[lab].enabled` only control tab availability. |
| `build-exe.ps1` | Windows convenience wrapper for production packaging. Runs PyInstaller through uv. |
| `build_exe.py` | Real exe build logic. Builds single-file `dist/RespiraScope.exe` by default. |

`dev.ps1` and `dev.py` are the same workflow at different layers: use
`dev.ps1` on Windows for convenience, or call `dev.py` directly when scripting.

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

The console is the single user-facing frontend entry. Documentation tabs are
opened through hash routes such as `/#guide` and `/#apiDocs`; the dev/prod logs
no longer print direct iframe file paths like `/guide/index.html`.

Avoid `uv run .venv/Scripts/python.exe scripts/build_exe.py`; that launches the
project venv Python and skips uv's temporary PyInstaller dependency.

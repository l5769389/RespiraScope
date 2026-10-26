# Scripts

The scripts folder is intentionally small:

| File | Purpose |
| --- | --- |
| `dev.ps1` | Windows convenience wrapper for local development. Runs `uv run respirascope --reload`. |
| `dev.py` | Compatibility wrapper for `uv run respirascope --reload`. Starts backend with reload and one Breath Console frontend when `[console].enabled = true`. Realtime Monitor and Mock Lab are the two built-in user-facing modes; `[monitor].enabled` and `[lab].enabled` control availability. |
| `build-exe.ps1` | Windows convenience wrapper for production packaging. Runs PyInstaller through uv. |
| `build-exe.bat` | Double-click Windows build entry; invokes PowerShell, preserves the exit code and keeps the result visible. |
| `build-macos-app.sh` | macOS convenience wrapper for production packaging. Builds launchable `dist/RespiraScope.app` that opens Terminal logs on startup. |
| `build_exe.py` | Real build logic. Builds a single executable by default, or a macOS app bundle with `--macos-app`. |

`dev.ps1` and `dev.py` are the same workflow at different layers: use
`dev.ps1` on Windows for convenience, or call `dev.py` directly when scripting.

The UI is plain HTML/CSS/JavaScript under `src/ct_breath/web/` and is
included in the Python package. Run `uv run respirascope` for normal use or
`uv run respirascope --reload` during development. UI edits take effect on
browser refresh; no separate JavaScript dependency installation or build is needed.

Install uv on Windows first (`winget install --id astral-sh.uv -e`, then reopen
the terminal). Double-click `build-exe.bat`, or run:

```powershell
.\scripts\build-exe.bat
.\scripts\build-exe.bat --onedir
```

The script downloads Python 3.13 and dependencies as needed, uses `uv.lock`, and
produces `dist/RespiraScope.exe`. Building requires internet on first use; the
result includes Python and the frontend and runs without uv, Python or Node.js
installed. Build on Windows: PyInstaller does not cross-compile Windows exe
files from macOS/Linux. The PowerShell wrapper remains available for automation
and returns the build exit code without pausing.

Launch the exe to open the standalone desktop window, with no terminal or browser.
Windows needs Microsoft Edge WebView2 Runtime. Closing the window stops the
services; save any records first. Logs are written to `%LOCALAPPDATA%/RespiraScope/logs/`,
and startup failures show a native error dialog. Both API and UI ports are bound
before use, with automatic fallback if occupied (including multiple instances).
The runtime frontend config receives the actual ports; TOML is not rewritten.
Windows defaults to `%LOCALAPPDATA%/RespiraScope/` for config and records and
still reads existing `D:/ct/breath-config/` configurations for compatibility.

Use `build-macos-app.sh` on macOS:

```bash
./scripts/build-macos-app.sh
```

The output is `dist/RespiraScope.app`, which can be opened from Finder or with:

```bash
open dist/RespiraScope.app
```

The app opens a Terminal window and runs the RespiraScope service there so the
startup URL and server logs stay visible. A copy of each launch log is also
written to `~/Library/Logs/RespiraScope/`.

The direct uv command is:

```bash
uv run --with "pyinstaller>=6.16" python scripts/build_exe.py
uv run --with "pyinstaller>=6.16" python scripts/build_exe.py --macos-app
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


## Offline binning comparison

`compare_shared_binning.py` measures all 14 simulator presets plus two local-cough
controls with 20 seeds each. It checks identical time/amplitude filter outputs,
then compares time, fixed-amplitude and relative-amplitude binning on that output.
`plot_shared_binning.py` creates the paired figures. Both run in the project uv environment:

```bash
uv run --frozen python scripts/compare_shared_binning.py
uv run --frozen python scripts/plot_shared_binning.py
```

Results, exact metric definitions, source hashes and seed-42 illustration data are
in `docs/measurements/shared_binning/`. `build_shared_binning_report.py` assembles
the DOCX using the document runtime's `python-docx`; render and visually check it
before distributing. The chart script currently uses the macOS Hiragino font.

The current report is `docs/时间分箱与固定幅值分箱波形对比.docx` (with a PDF
copy). Keep its measurements and paired figures together. Historical multi-filter
experiments and superseded overview charts are no longer part of this workflow.

`reference_binning_metrics.py` measures reference bin disagreement and amplitude
span change against the clean base signal. `raw_comparison_metrics.py` retains
the observed-input comparison in the measurement JSON. Their tests live in
`tests/`; neither module is used by the running application.

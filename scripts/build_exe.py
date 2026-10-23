import argparse
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path


PYINSTALLER_REQUIREMENT = "pyinstaller>=6.16"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def add_data_arg(source: Path, target: str) -> str:
    separator = ";" if sys.platform.startswith("win") else ":"
    return f"{source}{separator}{target}"


def build_command(root: Path, onedir: bool, app_bundle: bool) -> list[str]:
    mode = "--onedir" if onedir else "--onefile"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--console",
        mode,
        "--name",
        "RespiraScope",
        "--paths",
        str(root / "src"),
        "--collect-all",
        "numpy",
        "--collect-all",
        "scipy",
        "--collect-submodules",
        "socketio",
        "--collect-submodules",
        "engineio",
        "--collect-submodules",
        "uvicorn",
        "--hidden-import",
        "uvicorn.lifespan.on",
        "--hidden-import",
        "uvicorn.protocols.http.httptools_impl",
        "--hidden-import",
        "uvicorn.protocols.websockets.websockets_impl",
        "--hidden-import",
        "watchfiles",
        "--add-data",
        add_data_arg(root / "config" / "breath.example.toml", "config"),
        "--add-data",
        add_data_arg(root / "src" / "ct_breath" / "web" / "frontend-console", "frontend-console"),
        "--add-data",
        add_data_arg(root / "src" / "ct_breath" / "web" / "frontend-monitor", "frontend-monitor"),
        "--add-data",
        add_data_arg(root / "src" / "ct_breath" / "web" / "frontend-lab", "frontend-lab"),
        "--add-data",
        add_data_arg(root / "src" / "ct_breath" / "web" / "frontend-guide", "frontend-guide"),
        "--add-data",
        add_data_arg(root / "src" / "ct_breath" / "web" / "frontend-api-docs", "frontend-api-docs"),
    ]
    if sys.platform.startswith("win"):
        command.extend(["--icon", str(root / "src/ct_breath/web/frontend-console/assets/logo.ico")])
    command.append(str(root / "src" / "ct_breath" / "__main__.py"))
    return command


def copy_runtime_files(root: Path):
    package_dir = root / "dist" / "RespiraScope"
    if not package_dir.exists():
        return
    for name in ["frontend-console", "frontend-monitor", "frontend-lab", "frontend-guide", "frontend-api-docs", "config"]:
        source = root / name if name == "config" else root / "src" / "ct_breath" / "web" / name
        target = package_dir / name
        if target.exists():
            shutil.rmtree(target)
        if source.exists():
            shutil.copytree(source, target)


def clean_output(root: Path, onedir: bool, app_bundle: bool):
    dist = root / "dist"
    stale_file = dist / "RespiraScope.exe"
    stale_unix_file = dist / "RespiraScope"
    stale_dir = dist / "RespiraScope"
    stale_app = dist / "RespiraScope.app"

    if app_bundle:
        if stale_app.exists():
            shutil.rmtree(stale_app)
        if stale_dir.exists() and stale_dir.is_dir():
            shutil.rmtree(stale_dir)
        elif stale_unix_file.exists():
            stale_unix_file.unlink()
        if stale_file.exists():
            stale_file.unlink()
        return

    if onedir:
        if stale_file.exists():
            stale_file.unlink()
        return

    if stale_dir.exists() and stale_dir.is_dir():
        shutil.rmtree(stale_dir)
    elif stale_unix_file.exists():
        stale_unix_file.unlink()


def ensure_pyinstaller(root: Path, args: list[str]) -> bool:
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        if os.environ.get("CT_BREATH_BUILD_REEXEC") == "1":
            print("PyInstaller is not installed in this uv run.", file=sys.stderr)
            print(f"Use: uv run --with \"{PYINSTALLER_REQUIREMENT}\" python scripts/build_exe.py", file=sys.stderr)
            return False

        uv = shutil.which("uv")
        if uv is None:
            print("PyInstaller is not installed and uv was not found on PATH.", file=sys.stderr)
            print(f"Use: uv run --with \"{PYINSTALLER_REQUIREMENT}\" python scripts/build_exe.py", file=sys.stderr)
            return False

        command = [
            uv,
            "run",
            "--frozen",
            "--with",
            PYINSTALLER_REQUIREMENT,
            "python",
            "scripts/build_exe.py",
            *args,
        ]
        env = {**os.environ, "CT_BREATH_BUILD_REEXEC": "1"}
        result = subprocess.run(command, cwd=root, env=env)
        raise SystemExit(result.returncode)


def create_macos_app_bundle(root: Path):
    dist = root / "dist"
    payload_source = dist / "RespiraScope"
    app_dir = dist / "RespiraScope.app"
    contents_dir = app_dir / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"
    payload_target = resources_dir / "RespiraScope"

    if not payload_source.is_dir():
        raise FileNotFoundError(f"PyInstaller output was not found: {payload_source}")

    if app_dir.exists():
        shutil.rmtree(app_dir)
    macos_dir.mkdir(parents=True)
    resources_dir.mkdir(parents=True)
    shutil.move(str(payload_source), str(payload_target))
    shutil.copy2(root / "src/ct_breath/web/frontend-console/assets/logo.icns", resources_dir / "RespiraScope.icns")

    launcher = macos_dir / "RespiraScope"
    launcher.write_text(
        """#!/usr/bin/env bash
set -euo pipefail

APP_CONTENTS="$(cd "$(dirname "$0")/.." && pwd)"
PAYLOAD="$APP_CONTENTS/Resources/RespiraScope/RespiraScope"
LOG_DIR="$HOME/Library/Logs/RespiraScope"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/RespiraScope-$(date +%Y%m%d-%H%M%S).log"
RUN_COMMAND="$LOG_DIR/start-respirascope.command"
payload_quoted="$(printf "%q" "$PAYLOAD")"
log_file_quoted="$(printf "%q" "$LOG_FILE")"

cat > "$RUN_COMMAND" <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail
echo "[RespiraScope] Log file: $LOG_FILE"
echo
$payload_quoted 2>&1 | tee -a $log_file_quoted
SCRIPT

chmod +x "$RUN_COMMAND"
open -a Terminal "$RUN_COMMAND"
""",
        encoding="utf-8",
    )
    launcher.chmod(0o755)

    plist = {
        "CFBundleDisplayName": "RespiraScope",
        "CFBundleExecutable": "RespiraScope",
        "CFBundleIdentifier": "io.respirascope.app",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": "RespiraScope",
        "CFBundleIconFile": "RespiraScope.icns",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "NSHighResolutionCapable": True,
    }
    with (contents_dir / "Info.plist").open("wb") as plist_file:
        plistlib.dump(plist, plist_file)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build production RespiraScope executable with PyInstaller.")
    parser.add_argument("--onedir", action="store_true", help="Build an onedir package instead of the default single executable.")
    parser.add_argument("--onefile", action="store_false", dest="onedir", help=argparse.SUPPRESS)
    parser.add_argument("--macos-app", action="store_true", help="Build a launchable macOS .app bundle. Uses onedir mode because .app bundles are directories.")
    parser.add_argument("--dry-run", action="store_true", help="Print the PyInstaller command without running it.")
    args = parser.parse_args()

    if args.macos_app and not sys.platform == "darwin":
        print("--macos-app can only be used on macOS.", file=sys.stderr)
        return 2
    if args.macos_app:
        args.onedir = True

    root = project_root()
    command = build_command(root, args.onedir, args.macos_app)

    if args.dry_run:
        print(" ".join(command))
        return 0

    if not ensure_pyinstaller(root, sys.argv[1:]):
        return 2

    clean_output(root, args.onedir, args.macos_app)

    result = subprocess.run(command, cwd=root)
    if result.returncode != 0:
        return result.returncode

    if args.onedir:
        copy_runtime_files(root)
    if args.macos_app:
        create_macos_app_bundle(root)

    print("Build complete.")
    if args.macos_app:
        print(f"Output: {root / 'dist' / 'RespiraScope.app'}")
    elif args.onedir:
        print(f"Output: {root / 'dist' / 'RespiraScope'}")
    elif sys.platform.startswith("win"):
        print(f"Output: {root / 'dist' / 'RespiraScope.exe'}")
    else:
        print(f"Output: {root / 'dist' / 'RespiraScope'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

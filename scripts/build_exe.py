import argparse
import os
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


def build_command(root: Path, onedir: bool) -> list[str]:
    mode = "--onedir" if onedir else "--onefile"
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
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
        add_data_arg(root / "frontend-console", "frontend-console"),
        "--add-data",
        add_data_arg(root / "frontend-monitor", "frontend-monitor"),
        "--add-data",
        add_data_arg(root / "frontend-lab", "frontend-lab"),
        "--add-data",
        add_data_arg(root / "frontend-guide", "frontend-guide"),
        "--add-data",
        add_data_arg(root / "frontend-api-docs", "frontend-api-docs"),
        str(root / "src" / "ct_breath" / "__main__.py"),
    ]


def copy_runtime_files(root: Path):
    package_dir = root / "dist" / "RespiraScope"
    if not package_dir.exists():
        return
    for name in ["frontend-console", "frontend-monitor", "frontend-lab", "frontend-guide", "frontend-api-docs", "config"]:
        source = root / name
        target = package_dir / name
        if target.exists():
            shutil.rmtree(target)
        if source.exists():
            shutil.copytree(source, target)


def clean_output(root: Path, onedir: bool):
    dist = root / "dist"
    stale_file = dist / "RespiraScope.exe"
    stale_dir = dist / "RespiraScope"

    if onedir:
        if stale_file.exists():
            stale_file.unlink()
        return

    if stale_dir.exists():
        shutil.rmtree(stale_dir)


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
            "--with",
            PYINSTALLER_REQUIREMENT,
            "python",
            "scripts/build_exe.py",
            *args,
        ]
        env = {**os.environ, "CT_BREATH_BUILD_REEXEC": "1"}
        result = subprocess.run(command, cwd=root, env=env)
        raise SystemExit(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build production RespiraScope executable with PyInstaller.")
    parser.add_argument("--onedir", action="store_true", help="Build an onedir package instead of the default single exe.")
    parser.add_argument("--onefile", action="store_false", dest="onedir", help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", action="store_true", help="Print the PyInstaller command without running it.")
    args = parser.parse_args()

    root = project_root()
    command = build_command(root, args.onedir)

    if args.dry_run:
        print(" ".join(command))
        return 0

    if not ensure_pyinstaller(root, sys.argv[1:]):
        return 2

    clean_output(root, args.onedir)

    result = subprocess.run(command, cwd=root)
    if result.returncode != 0:
        return result.returncode

    if args.onedir:
        copy_runtime_files(root)

    print("Build complete.")
    if args.onedir:
        print(f"Output: {root / 'dist' / 'RespiraScope'}")
    else:
        print(f"Output: {root / 'dist' / 'RespiraScope.exe'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

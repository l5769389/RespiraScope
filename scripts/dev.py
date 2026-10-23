"""Compatibility wrapper for the uv-managed development entry point."""
import sys

from ct_breath.main import main


if __name__ == "__main__":
    raise SystemExit(main(["--reload", *sys.argv[1:]]))

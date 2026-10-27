if __name__ == "__main__":
    from multiprocessing import freeze_support

    freeze_support()
    import sys

    if getattr(sys, "frozen", False) and sys.platform == "win32":
        from ct_breath.runtime.desktop import desktop_main as main
    else:
        from ct_breath.main import main

    raise SystemExit(main())

"""Windows desktop host. The GUI owns the lifetime of the local services."""

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from time import monotonic


def run_desktop(server, sockets, console_url):
    import webview

    finished = Event()
    closing = Event()
    failures = []

    def serve():
        try:
            server.run(sockets=sockets)
        except BaseException as exc:
            failures.append(exc)
        finally:
            finished.set()

    worker = Thread(target=serve, name='desktop-backend', daemon=True)
    worker.start()
    try:
        deadline = monotonic() + 30
        while not server.started:
            if finished.wait(0.05):
                raise RuntimeError(f'Backend startup failed: {failures[0] if failures else "service stopped"}')
            if monotonic() >= deadline:
                raise RuntimeError('Backend startup timed out.')

        # Record exports use browser downloads; pywebview disables them by default.
        webview.settings['ALLOW_DOWNLOADS'] = True
        window = webview.create_window(
            'RespiraScope', console_url, width=1440, height=960,
            min_size=(960, 640), background_color='#F4F7FB',
        )

        def watch_backend():
            while not closing.wait(0.25):
                if finished.is_set():
                    window.destroy()
                    return

        # Force Chromium: the deprecated IE fallback cannot render this UI.
        webview.start(func=watch_backend, gui='edgechromium', debug=False)
        if finished.is_set() and not server.should_exit:
            raise RuntimeError(f'Backend stopped unexpectedly: {failures[0] if failures else "see log"}')
    finally:
        closing.set()
        server.should_exit = True
        worker.join(timeout=10)
        if worker.is_alive():
            raise RuntimeError('Backend shutdown timed out.')


def desktop_main(argv=None):
    """Windowed executables have no stdout/stderr; establish logging before imports."""
    log_path = None
    log_file = None
    previous_streams = sys.stdout, sys.stderr
    try:
        root = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData/Local') / 'RespiraScope'
        log_dir = root / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f'app-{datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}.log'
        log_file = log_path.open('a', encoding='utf-8', buffering=1)
        sys.stdout = sys.stderr = log_file
        from ct_breath.main import main

        return main(argv, desktop=True)
    except (Exception, SystemExit) as exc:
        if isinstance(exc, SystemExit) and not exc.code:
            return 0
        if log_file:
            traceback.print_exc(file=log_file)
        import ctypes

        message = (f'应用启动或运行失败：\n{exc}\n\n'
                   f'日志：{log_path or "无法创建日志文件"}\n\n'
                   '若提示缺少 WebView2，请安装 Microsoft Edge WebView2 Runtime。')
        ctypes.windll.user32.MessageBoxW(None, message, 'RespiraScope', 0x10)
        return 1
    finally:
        sys.stdout, sys.stderr = previous_streams
        if log_file:
            log_file.close()

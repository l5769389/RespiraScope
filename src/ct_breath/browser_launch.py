"""Open the local console once, outside the server and reload worker threads."""

import webbrowser
from threading import Event, Thread
from time import monotonic
from urllib.request import ProxyHandler, build_opener


def open_when_ready(console_url: str, health_url: str, stopped: Event):
    # Local readiness checks must not go through a system HTTP proxy.
    opener = build_opener(ProxyHandler({}))
    deadline = monotonic() + 60
    while not stopped.is_set() and monotonic() < deadline:
        try:
            for url in (health_url, console_url):
                with opener.open(url, timeout=0.5) as response:
                    if response.status != 200:
                        raise OSError('Service is not ready')
        except OSError:
            stopped.wait(0.25)
            continue
        if stopped.is_set():
            return
        try:
            if webbrowser.open(console_url, new=2):
                return
        except (OSError, webbrowser.Error):
            pass
        print(f'[RespiraScope] Could not open a browser. Open Console manually: {console_url}', flush=True)
        return
    if not stopped.is_set():
        print(f'[RespiraScope] Still waiting for services. Open Console manually when ready: {console_url}', flush=True)


def start_browser_when_ready(console_url: str, health_url: str):
    stopped = Event()
    worker = Thread(target=open_when_ready, args=(console_url, health_url, stopped),
                    name='console-browser', daemon=True)
    worker.start()

    def stop():
        stopped.set()
        worker.join(timeout=1.5)

    return stop

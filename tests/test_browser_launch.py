import threading
from contextlib import contextmanager
from unittest.mock import Mock
from urllib.error import URLError

import pytest

from ct_breath import main


def test_browser_can_be_disabled_from_command_line():
    assert main.parse_args(['--no-browser']).no_browser


def test_browser_waits_for_both_services_then_opens_only_once(monkeypatch):
    from ct_breath import browser_launch

    requested = []
    opened = []

    @contextmanager
    def request(url, timeout):
        requested.append(url)
        if len(requested) == 1:
            raise URLError('still starting')
        yield Mock(status=200)

    monkeypatch.setattr(browser_launch, 'build_opener', lambda *args: Mock(open=request))
    monkeypatch.setattr(browser_launch.webbrowser, 'open', lambda url, **kwargs: opened.append(url) or True)
    browser_launch.open_when_ready('http://localhost:5176/console/', 'http://localhost:8001/health', threading.Event())
    assert requested == ['http://localhost:8001/health'] * 2 + ['http://localhost:5176/console/']
    assert opened == ['http://localhost:5176/console/']


def test_stopping_startup_cancels_browser_launch(monkeypatch):
    from ct_breath import browser_launch

    stopped = threading.Event()
    stopped.set()
    opened = []
    monkeypatch.setattr(browser_launch.webbrowser, 'open', lambda *args, **kwargs: opened.append(args))
    browser_launch.open_when_ready('http://localhost:5175/', 'http://localhost:8000/health', stopped)
    assert opened == []


@pytest.mark.parametrize('failure', [False, OSError('browser unavailable')])
def test_browser_failure_leaves_a_manual_url_without_crashing(monkeypatch, capsys, failure):
    from ct_breath import browser_launch

    @contextmanager
    def request(*args, **kwargs):
        yield Mock(status=200)

    def open_browser(*args, **kwargs):
        if isinstance(failure, Exception):
            raise failure
        return failure

    monkeypatch.setattr(browser_launch, 'build_opener', lambda *args: Mock(open=request))
    monkeypatch.setattr(browser_launch.webbrowser, 'open', open_browser)
    browser_launch.open_when_ready('http://localhost:5175/', 'http://localhost:8000/health', threading.Event())
    assert 'http://localhost:5175/' in capsys.readouterr().out


def test_readiness_timeout_does_not_open_browser(monkeypatch, capsys):
    from ct_breath import browser_launch

    times = iter([0, 61])
    opened = []
    monkeypatch.setattr(browser_launch, 'monotonic', lambda: next(times))
    monkeypatch.setattr(browser_launch.webbrowser, 'open', lambda *args, **kwargs: opened.append(args))
    browser_launch.open_when_ready('http://localhost:5175/', 'http://localhost:8000/health', threading.Event())
    assert opened == []
    assert 'http://localhost:5175/' in capsys.readouterr().out

"""Source and frozen distributions must serve the same resource layout."""
import sys
import threading
from urllib.request import urlopen

import pytest

from ct_breath.core.config import AppConfig
from ct_breath.runtime import resources
from ct_breath.runtime.static_server import create_static_server
from scripts.packaging.build_exe import add_data_arg, build_command, project_root


def test_packaging_embeds_the_resource_tree_used_by_frozen_runtime(monkeypatch, tmp_path):
    root = project_root()
    command = build_command(root, onedir=True, app_bundle=False)
    destination = 'ct_breath/web'
    assert add_data_arg(root / 'src' / destination, destination) in command
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    assert resources.web_root() == tmp_path / destination


@pytest.mark.parametrize('base', ['', '/respira'])
def test_static_routes_work_outside_project_directory(monkeypatch, tmp_path, base):
    monkeypatch.chdir(tmp_path)
    config = AppConfig(public_base_path=base)
    server, _ = create_static_server('console', '127.0.0.1', 0, config)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for route in ['/', '/monitor/', '/lab/', '/guide/', '/api-docs/',
                      '/shared/runtime.js', '/shared/filtered-series.js',
                      '/assets/logo.svg', '/vendor/echarts.min.js',
                      '/vendor/socket.io.min.js', '/runtime-config.js']:
            with urlopen(f'http://127.0.0.1:{server.server_port}{base}{route}', timeout=5) as response:
                assert response.status == 200
                assert response.read(), route
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

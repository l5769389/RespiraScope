"""Recording must retain real context before filtering a short selected interval."""
import asyncio

import numpy as np
from fastapi.testclient import TestClient

from ct_breath.app import create_app
from ct_breath.config import AppConfig
from ct_breath.frontend_static import runtime_config_payload
from ct_breath.breath_process.breath_process_manager import BreathProcessSystem
from ct_breath.breath_process.offline_quality import filter_offline
from ct_breath.http.schemas import FilterConfig, normalize_filter_config


def test_configured_long_context_keeps_legacy_bandpass_record_usable():
    system = BreathProcessSystem(AppConfig(record_pre_points=1000, record_post_points=1000))
    manager = system.record_manager
    t = np.arange(15000)/50
    p = 2*np.pi*.3*t
    raw = 180+110*(.82*np.sin(p)+.18*np.sin(2*p-.8)+.06*np.sin(3*p+.4))
    for i in range(7500):
        manager.handle_data(i, raw[i])
    manager.start_record()
    for i in range(7500,9000):
        manager.handle_data(i, raw[i])
    manager.stop_record()
    for i in range(9000,9000+manager.post_points):
        manager.handle_data(i, raw[i])
    points = manager.raw_points_for_filter()
    y,q = filter_offline([p[1] for p in points], [p[0] for p in points],
                        normalize_filter_config(FilterConfig(processing_mode='amplitude')))
    selection = np.array([7500 <= p[0] < 9000 for p in points])
    assert q['baselines'][0]['status'] == 'estimated'
    assert not any(i['start'] < 9000 and i['end'] > 7500 for i in q['invalidIntervals'])
    assert np.sqrt(np.mean((y[selection]-raw[7500:9000])**2)) < 2
    assert manager.record_start_sequence == 7500 and manager.record_end_sequence == 8999
    assert manager.record_complete


def test_runtime_and_browser_publish_effective_padding():
    config = AppConfig(record_pre_points=100,record_post_points=1800)
    system = BreathProcessSystem(config)
    client = TestClient(create_app(config))
    api = client.get('/runtime/config').json()['data']['record']
    browser = runtime_config_payload(config)['record']
    assert api['pre_points'] == 100  # Explicit configuration is not automatically enlarged.
    assert api['pre_points'] == browser['prePoints'] == system.record_manager.pre_points
    assert api['post_points'] == browser['postPoints'] == system.record_manager.post_points == 1800


def test_post_wait_allows_twenty_seconds_of_samples(monkeypatch):
    system = BreathProcessSystem(AppConfig())
    manager = system.record_manager
    manager.post_points = 1000
    manager.handle_data(0,180)
    manager.start_record()
    manager.handle_data(1,180)
    manager.stop_record()
    elapsed = [0.0]
    class Clock:
        def time(self): return elapsed[0]
    async def advance(_):
        elapsed[0] += 1
        for seq in range(int(elapsed[0]-1)*50+2,int(elapsed[0])*50+2):
            manager.handle_data(seq,180)
    async def run():
        monkeypatch.setattr(asyncio,'get_running_loop',lambda:Clock())
        monkeypatch.setattr(asyncio,'sleep',advance)
        await system._wait_for_post_record_padding(None)
    asyncio.run(run())
    assert manager.record_complete
    assert len(manager.raw_record_queue) >= 1001


def test_filter_change_keeps_configured_context_and_history():
    system = BreathProcessSystem(AppConfig())
    manager = system.record_manager
    for i in range(500): manager.handle_data(i,180)
    old = list(manager.raw_pre_buffer)
    system.update_filter_config(normalize_filter_config(FilterConfig(
        processing_mode='amplitude',bandpass_mode='custom',lowpass_cutoff=.01,highpass_cutoff=2)))
    assert manager.pre_points == 200
    assert list(manager.raw_pre_buffer) == old

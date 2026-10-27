"""Shared offline filtering scenarios and record assertions."""
import numpy as np
from ct_breath.recording.manager import RecordManager
from ct_breath.recording.serialization import compact_record_data
from ct_breath.models import FilterConfig
from tests.support.storage import stored_bins

def wave(seconds=180):
    t = np.arange(seconds * 50) / 50
    phase = 2 * np.pi * .3 * t
    return 180 + 110 * (.82*np.sin(phase) + .18*np.sin(2*phase-.8) + .06*np.sin(3*phase+.4))


def apply(client, values, **config):
    raw = [[i, float(y)] for i, y in enumerate(values)]
    response = client.post('/applyFilter', json={'raw_data':raw, 'filter_config':{
        'processing_mode':'amplitude', **config,
    }})
    assert response.status_code == 200
    return response.json()


def record_bins(values, result, mode):
    manager = RecordManager()
    manager.record_start_sequence, manager.record_end_sequence = 1000, len(values)-1001
    manager.raw_record_queue.extend([[i,float(v)] for i,v in enumerate(values)])
    record = manager.build_record_data(FilterConfig(**result['filter_config']),
        filtered_data=result['data'], peak_data=result['peak'], valley_data=result['valley'],
        processing_quality=result['processingQuality'],
        analysis={'basis':mode,'amplitudeMode':'fixed','lower':100,'upper':250})
    return stored_bins(compact_record_data(record))

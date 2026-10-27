"""Shared measured-breath scenarios for backend and browser parity tests."""
from ct_breath.binning.respiratory import build_respiratory_bins

FIXED = dict(basis='amplitude', amplitudeMode='fixed', lower=0, upper=50, inhaleRising=True, totalBins=10)


TIME = {**FIXED, 'basis':'time'}


def triangle():
    return {'filtered': [[i, i if i <= 50 else 100-i] for i in range(101)],
            'peaks': [[50,50]], 'valleys': [[0,0]]}


def compute(source, options=FIXED):
    points = lambda key: [dict(sequence=x, value=y) for x,y in source.get(key, [])]
    return build_respiratory_bins(points('filtered'), points('peaks'), points('valleys'), options,
        invalid_intervals=source.get('processingQuality',{}).get('invalidIntervals',[]))


def missed_turn():
    return {'filtered':[[i, abs(i-50)] for i in range(101)], 'peaks':[[0,50],[100,50]], 'valleys':[]}

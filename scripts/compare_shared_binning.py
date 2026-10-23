"""Measure time/fixed/free binning on the identical offline low-pass result.

uv run --frozen python scripts/compare_shared_binning.py
All built-in presets, seeds 42..61; synthetic data only.
"""
from __future__ import annotations
import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path
import numpy as np
from fastapi.testclient import TestClient
from ct_breath.app import create_app
from ct_breath.config import AppConfig
from ct_breath.mock_sensor.breath_simulator import SCENARIO_PRESETS, BreathWaveform
from ct_breath.breath_process.respiratory_bins import build_respiratory_bins
from raw_comparison_metrics import compare_to_raw, summarize_raw_comparison
from reference_binning_metrics import (reference_labels, compare_reference, summarize_reference,
                                      compare_base_span, summarize_base_span)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/measurements/shared_binning'
FS, START, STOP = 50, 9000, 12000
SEEDS = list(range(42,62))
NAMES = dict(zip(SCENARIO_PRESETS, ['正常呼吸','呼吸急促','呼吸过缓','浅呼吸','不规则呼吸',
    '屏气与呼吸暂停','噪声干扰','体动伪影','深呼吸','快速浅呼吸','基线漂移','周期性减弱','低幅强噪声','密集咳嗽与冲击伪影']))
MODES = ['time','fixed','free']


def labels_from_bins(bins, start=START, stop=STOP):
    labels = np.full(stop-start, -1, dtype=int)
    for b in bins:
        a, z = max(start, math.ceil(b['start'])), min(stop, math.ceil(b['end']))
        if z <= a: continue
        number = (0 if b['direction']=='inhale' else 5)+b['bin']-1
        assert (labels[a-start:z-start] == -1).all(), 'Overlapping bins'
        labels[a-start:z-start] = number
    return labels


def within_bin_spread(truth, labels, mask, scale):
    """Sample-weighted population SD within each direction/bin, then / scale."""
    n, squared = 0, 0.
    for group in range(10):
        values = truth[mask & (labels==group)]
        if len(values):
            n += len(values)
            squared += float(np.sum((values-values.mean())**2))
    return 100*math.sqrt(squared/n)/scale if n else None


def default_bounds(data, quality, start=START, end=STOP-1):
    # Same floor-quantile and record-only convention as defaultAmplitudeBounds in UI.
    invalid = quality['invalidIntervals']
    values = sorted(y for x,y in data if start<=x<=end and
                    not any(iv['start']<=x<iv['end'] for iv in invalid))
    if not values: return [0.,100.]
    low, high = [float(values[math.floor((len(values)-1)*q)]) for q in [.05,.95]]
    return [low,max(low+.1,high)]


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    client = TestClient(create_app(AppConfig(enable_front_console=False,
        record_pre_points=1000,record_post_points=1000)))
    cases = [(sid,cfg,NAMES[sid],[]) for sid,cfg in SCENARIO_PRESETS.items()]
    cases += [('local_cough',SCENARIO_PRESETS['normal'],'单次局部咳嗽',[203]),
              ('repeated_cough',SCENARIO_PRESETS['normal'],'间歇局部咳嗽',[190,205,220,235])]
    rows = []
    phase=np.linspace(0,2*np.pi,10001)
    unit_shape=.82*np.sin(phase)+.18*np.sin(2*phase-.8)+.06*np.sin(3*phase+.4)
    for sid,cfg,name,cough_times in cases:
        samples=[]; errors=[]; examples=None
        scale=float(cfg.amplitude*np.ptp(unit_shape))
        for seed in SEEDS:
            wave=BreathWaveform(lambda:cfg,seed=seed)
            raw=[]; truth=[]
            for i in range(15000):
                t=i/FS
                raw.append([i,wave.value_at(t)])
                truth.append(cfg.baseline+cfg.drift*math.sin(2*math.pi*t/45)+
                             wave._apnea_scale(cfg,t)*cfg.amplitude*wave._breath_shape(wave.phase))
            for t in cough_times:
                for k in range(20): raw[t*FS+k][1] += 400*(19-k)/19
            results=[]
            for basis in ['time','amplitude']:
                response=client.post('/applyFilter',json={'raw_data':raw[8000:13000],
                    'filter_config':{'processing_mode':basis,'offline_filter':'baseline_lowpass',
                        'bandpass_mode':'custom','highpass_cutoff':2.,'lowpass_order':4,
                        'gaussian_sigma':1.,'peak_threshold_ratio':.3},
                    'record_start_sequence':START,'record_end_sequence':STOP-1})
                assert response.status_code==200,response.text
                results.append(response.json())
            for key in ['data','peak','valley','processingQuality']:
                assert results[0][key]==results[1][key],(sid,seed,key)
            r=results[0]; quality=r['processingQuality']; invalid=quality['invalidIntervals']
            data=np.asarray(r['data']); assert data[0,0]==8000 and data[-1,0]==12999
            seq=np.arange(START,STOP); valid=np.ones(len(seq),dtype=bool)
            for iv in invalid: valid &= ~((seq>=iv['start']) & (seq<iv['end']))
            clean=np.asarray(truth)[START:STOP]; filtered=data[1000:4000,1]
            errors.extend(((filtered[valid]-clean[valid])/scale*100).tolist())
            bounds=default_bounds(r['data'],quality)
            point=lambda pairs:[{'sequence':p[0],'value':p[1]} for p in pairs]
            labels={}; bins={}
            for mode in MODES:
                options={'basis':'time' if mode=='time' else 'amplitude','amplitudeMode':'fixed' if mode=='fixed' else 'free',
                    'totalBins':10,'inhaleRising':True,'lower':bounds[0],'upper':bounds[1]}
                bins[mode]=build_respiratory_bins(point(r['data']),r['peak'],r['valley'],options,
                    start=START,end=STOP-1,invalid_intervals=invalid)
                for b in bins[mode]:
                    assert all(not (b['start']<iv['end'] and b['end']>iv['start']) for iv in invalid)
                labels[mode]=labels_from_bins(bins[mode])
                assert not ((labels[mode]>=0) & ~valid).any()
            common=(labels['time']>=0)&(labels['fixed']>=0)
            per={'seed':seed,'bounds':bounds,'valid_percent':float(valid.mean()*100),
                 'common_percent':float(common.mean()*100),'modes':{},
                 'raw_comparison':compare_to_raw(np.asarray(raw)[START:STOP,1],filtered,valid,FS,cfg.bpm)}
            reference = {key: value[START:STOP] for key, value in reference_labels(truth, bounds).items()}
            per['reference_comparison'] = compare_reference(labels, reference, valid)
            per['base_span_comparison'] = compare_base_span(clean, filtered, valid)
            for mode in MODES:
                per['modes'][mode]={'coverage':float(np.mean(labels[mode]>=0)*100),
                    'occupied_bins':int(len(set(labels[mode]) - {-1})),
                    'spread':within_bin_spread(clean,labels[mode],common,scale) if mode!='free' else None}
            samples.append(per)
            if seed==42:
                examples={'raw':raw[8000:13000], 'truth':truth[8000:13000],'filtered':r['data'],
                    'peaks':r['peak'],'valleys':r['valley'],'quality':quality,'bounds':bounds,'bins':bins,
                    'metrics':per}
                (OUT/f'{sid}.json').write_text(json.dumps(examples,ensure_ascii=False,separators=(',',':')))
        e=np.asarray(errors)
        row={'id':sid,'name':name,'preset':asdict(cfg),'cough_seconds':cough_times,'scale':scale,
             'valid_percent':float(np.mean([s['valid_percent'] for s in samples])),
             'common_percent':float(np.mean([s['common_percent'] for s in samples])),
             'filter_nrmse':float(np.sqrt(np.mean(e**2))) if len(e) else None,
             'filter_error_p95':float(np.percentile(np.abs(e),95)) if len(e) else None,
             'filter_scored_points':len(e),'identical_filter_results':True,'modes':{},'seeds':samples}
        row['raw_comparison']=summarize_raw_comparison([s['raw_comparison'] for s in samples])
        row['reference_comparison']=summarize_reference([s['reference_comparison'] for s in samples])
        row['base_span_comparison']=summarize_base_span([s['base_span_comparison'] for s in samples])
        for mode in MODES:
            spread=[s['modes'][mode]['spread'] for s in samples if s['modes'][mode]['spread'] is not None]
            row['modes'][mode]={'coverage':float(np.mean([s['modes'][mode]['coverage'] for s in samples])),
                'spread':float(np.mean(spread)) if spread else None,'spread_seed_count':len(spread),
                'zero_coverage_seeds':sum(s['modes'][mode]['coverage']==0 for s in samples)}
        rows.append(row)
        print(name,[(m,round(row['modes'][m]['coverage'],1),row['modes'][m]['spread']) for m in MODES],flush=True)
    sources=['scripts/compare_shared_binning.py','scripts/raw_comparison_metrics.py','scripts/reference_binning_metrics.py','src/ct_breath/breath_process/filter_context.py',
        'src/ct_breath/breath_process/offline_quality.py','src/ct_breath/breath_process/peak_valley_detector.py',
        'src/ct_breath/breath_process/respiratory_bins.py','src/ct_breath/mock_sensor/breath_simulator.py']
    payload={'sampling_rate':FS,'seeds':SEEDS,'record_seconds':[START/FS,STOP/FS],
        'buffer_samples_per_side':1000,'filter':{'method':'Butterworth SOS forward-backward lowpass','order':4,
            'cutoff_hz':2,'gaussian_sigma':1,'peak_threshold_ratio':.3},
        'definitions':{'reference':'Analytic simulator output including configured baseline drift; before noise, artifacts, clipping and rounding.',
            'scale':'Nominal unmodulated simulator breath peak-to-peak amplitude; constant per scenario.',
            'coverage':'Percent of the 3000 one-minute samples assigned a direction and bin; intervals [start,end). Record end=11999 leaves the endpoint unassigned.',
            'spread':'On exactly the time/fixed common assigned samples of each seed, sqrt(sum within-group squared deviations / sample count) / scale * 100. Groups = direction x bin (10). Mean over contributing seeds; lower means more concentrated reference signal amplitude, NOT organ position accuracy.',
            'filter_nrmse':'sqrt(mean((filtered-reference)^2))/scale*100 on quality-valid one-minute samples, pooled over seeds.',
            'filter_error_p95':'95th percentile of absolute point error/scale*100 on quality-valid samples, pooled over seeds.',
            'bounds':'Floor-rank P5/P95 of quality-valid filtered samples inside record; shared across all cycles, re-estimated per seed.',
            'missing':'No common binned samples -> null spread, not zero. Valid samples / bin coverage do not prove physiological correctness.'},
        'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'rows':rows}
    payload['definitions']['raw_comparison']={
        'population':'Quality-valid samples in each 60-second record; raw means the observed input including noise. These are differences, not errors versus truth.',
        'mae':'Mean absolute filtered-minus-raw difference at the same timestamp, no lag compensation. Report physical simulation units and percent of that run raw P95-P5 span. Arithmetic mean over runs.',
        'span_change':'100 * ((filtered P95-P5)/(raw P95-P5)-1), both on identical valid samples. Arithmetic mean over runs; negative means narrower amplitude span.',
        'lag':'Maximize demeaned within-region normalized cross-correlation over +/-500 ms on the 20 ms grid. Positive means processed later. Only contiguous valid regions with >=2 nominal periods after both 500 ms guards; same raw anchors for every lag; require correlation >=0.5 and non-search-edge maximum. No estimate is null. Median signed lag across eligible runs; P95 absolute lag and count also retained.',
        'limitation':'Whole-waveform alignment is not individual extrema timing or frequency-specific phase response. Zero grid lag cannot establish zero local timing error.'}
    payload['definitions']['reference_comparison']={
        'reference': 'Sampled local extrema of the full analytic noise/artifact-free waveform, detected independently by scipy.signal.find_peaks with no smoothing or thresholds. Includes baseline drift and preset amplitude modulation. Never uses production extrema or build_respiratory_bins.',
        'time': 'Split each clean reference extremum-to-opposite-extremum half-breath into five equal time parts; rising=inhale. Reference unavailable outside complete reference halves.',
        'fixed': 'Classify the clean value directly into five equal amplitude bands using the SAME per-run app bounds; add clean reference direction. Clean value outside bounds has label -1 and counts as mismatch if actual fixed assigned a bin.',
        'population': 'Exactly the same quality-valid samples assigned by both actual modes and inside a reference half-breath. No reference amplitude-in-range restriction. Denominator and number of contributing runs are retained in measurement JSON.',
        'mismatch': 'Actual direction/bin differs from its own method reference direction/bin, or actual fixed assigns a bin outside the clean reference amplitude range. Pooled counts over 20 runs, percent of scored samples.',
        'limitations': 'Compares agreement with each method own reference, not common physiological target or CT quality. Does not score unassigned samples as correct. Synthetic apnea/weakening retain 8 percent oscillation; reference labels here do not establish clinical apnea detection.'}
    payload['definitions']['base_span_comparison']={
        'reference': 'Analytic noise/artifact-free base signal, including configured baseline drift and amplitude modulation; no production filtering applied.',
        'population': 'Identical finite quality-valid timestamps in each 60-second record for clean and filtered signals, independent of bin assignment. Excluded artifact intervals are not scored.',
        'span': '95th percentile minus 5th percentile (numpy linear interpolation) of sample values; not a mean per-cycle peak-to-trough amplitude.',
        'change': '100 * (filtered span / clean span - 1). Negative means narrower; positive means wider. Arithmetic mean of available per-run changes over 20 runs. Empty or zero reference span returns null.',
        'limitations': 'Shared filtering yields identical results for both binning modes. This measures amplitude-span change, not pointwise waveform accuracy or baseline offset; positive and negative changes across runs can cancel.'}
    (OUT/'metrics.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False))

if __name__=='__main__':main()

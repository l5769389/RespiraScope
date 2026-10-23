"""Reproduce the three offline filter comparisons with known simulator truth.
Run: uv run --frozen python scripts/measure_filter_amplitude.py
No app parameters or saved patient records are changed.
"""
from __future__ import annotations
import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path
import numpy as np
from scipy.signal import find_peaks
from fastapi.testclient import TestClient
from ct_breath.app import create_app
from ct_breath.config import AppConfig
from ct_breath.http.schemas import FilterConfig
from ct_breath.mock_sensor.breath_simulator import SCENARIO_PRESETS, BreathWaveform
from ct_breath.breath_process.record_manager import RecordManager
from ct_breath.breath_process.record_file import compact_record_data

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/measurements/three_mode_amplitude.json'
FS, START, STOP = 50, 9000, 12000
SEEDS = list(range(42, 62))
MODES = ('time', 'amplitude', 'baseline_lowpass')
NAMES = ['正常呼吸','呼吸急促','呼吸过缓','浅呼吸','不规则呼吸','屏气与呼吸暂停','噪声干扰','体动伪影','深呼吸','快速浅呼吸','基线漂移','周期性减弱','低幅强噪声','密集咳嗽与冲击伪影']


def summarize(values):
    a = np.asarray(values, dtype=float)
    return {'count': len(a), 'mean': float(a.mean()), 'p95': float(np.percentile(a,95))} if len(a) else {'count':0,'mean':None,'p95':None}


def valid_mask(result):
    seq = np.asarray(result['data'])[:,0].astype(int)
    y = np.full(15000, np.nan)
    y[seq] = np.asarray(result['data'])[:,1]
    valid = np.isfinite(y)
    valid[:START] = False; valid[STOP:] = False
    for iv in result['processingQuality']['invalidIntervals']:
        valid[max(0,iv['start']):min(15000,iv['end'])] = False
    return y, valid


def main():
    Path('/private/tmp/respirascope-three-mode-measurement').mkdir(parents=True, exist_ok=True)
    client = TestClient(create_app(AppConfig(enable_mock_signal=True, enable_front_console=False)))
    # Historical report reproduction: explicitly retain its former 5-second time context.
    historical_time_client = TestClient(create_app(AppConfig(enable_front_console=False,
        record_pre_points=250, record_post_points=250)))
    # A separate app makes the equal-context control explicit.
    equal_client = TestClient(create_app(AppConfig(enable_mock_signal=True, enable_front_console=False,
        record_time_pre_points=1000, record_time_post_points=1000)))
    cases = [(key,cfg,name,[]) for (key,cfg),name in zip(SCENARIO_PRESETS.items(),NAMES)]
    cases += [('local_cough',SCENARIO_PRESETS['normal'],'单次局部咳嗽',[203]),
              ('repeated_cough',SCENARIO_PRESETS['normal'],'间歇局部咳嗽',[190,205,220,235])]
    rows = []
    for sid,cfg,name,cough_times in cases:
        all_errors = {mode:[] for mode in MODES}; all_bias = {mode:[] for mode in MODES}
        seed_rows = []; point_errors = {mode:[] for mode in MODES}; no_drift_errors = {mode:[] for mode in MODES}
        context_errors = {mode:[] for mode in ('time5','time20')}
        full_cycles = None
        for seed in SEEDS:
            wave = BreathWaveform(lambda:cfg, seed=seed)
            raw,truth,physio,carrier = [],[],[],[]
            for i in range(15000):
                t=i/FS
                raw.append([i,wave.value_at(t)])
                shape=cfg.amplitude*wave._breath_shape(wave.phase)
                breath=wave._apnea_scale(cfg,t)*shape
                physio.append(cfg.baseline+breath)
                truth.append(cfg.baseline+cfg.drift*math.sin(2*math.pi*t/45)+breath)
                carrier.append(shape)
            for second in cough_times:
                for k in range(20):raw[second*FS+k][1] += 400*(19-k)/19
            truth=np.asarray(truth);physio=np.asarray(physio)
            # Ground-truth oscillator cycles; no detected output extrema are used for scoring.
            valleys=find_peaks(-np.asarray(carrier),distance=max(1,int(.5*FS*60/cfg.bpm)),prominence=cfg.amplitude*.15)[0]
            cycles=[(int(a),int(b)) for a,b in zip(valleys[:-1],valleys[1:]) if START<=a<b<STOP and np.ptp(truth[a:b+1])>5]
            full_cycles=len(cycles)
            scale=float(np.median([np.ptp(physio[a:b+1]) for a,b in cycles]))
            assert scale>0
            manager=RecordManager();manager.raw_record_queue.extend(raw[8000:13000])
            manager.record_start_sequence,manager.record_end_sequence=START,STOP-1
            results={};ys={};masks={}
            for mode in (*MODES,'time20'):
                is_time=mode in ('time','time20')
                config=FilterConfig(processing_mode='time' if is_time else 'amplitude',
                    offline_filter='baseline_lowpass' if mode=='baseline_lowpass' else 'bandpass',
                    order=1,lowpass_order=4,gaussian_sigma=1,peak_threshold_ratio=.3)
                r=(equal_client if mode=='time20' else historical_time_client if mode in ('time',) else client).post('/applyFilter',json={
                    'raw_data':raw[8000:13000], 'filter_config':config.model_dump(),
                    'record_start_sequence':START,'record_end_sequence':STOP-1})
                assert r.status_code==200,r.text
                result=r.json();results[mode]=result
                assert result['data'][0][0]==(8750 if mode=='time' else 8000)
                assert result['data'][-1][0]==(12249 if mode=='time' else 12999)
                assert result['filter_config']['highpass_cutoff']==(40/60 if is_time else 2)
                ys[mode],masks[mode]=valid_mask(result)
            bounds_values=sorted(v for s,v in results['amplitude']['data'] if not any(iv['start']<=s<iv['end'] for iv in results['amplitude']['processingQuality']['invalidIntervals']))
            lower=bounds_values[math.floor((len(bounds_values)-1)*.05)] if bounds_values else 0.
            upper=bounds_values[math.floor((len(bounds_values)-1)*.95)] if bounds_values else 100.
            upper=max(lower+.1,upper)
            common=np.logical_and.reduce([masks[m] for m in MODES])
            accepted=[(a,b) for a,b in cycles if common[a:b+1].all()]
            per={'seed':seed,'normalization_span':scale,'truth_cycles':len(cycles),
                 'common_valid_seconds':float(common.sum()/FS),'paired_cycles':len(accepted),'bounds':[lower,upper],'modes':{}}
            for mode in MODES:
                signed=[100*(np.ptp(ys[mode][a:b+1])/np.ptp(truth[a:b+1])-1) for a,b in accepted]
                errs=np.abs(signed).tolist(); all_errors[mode].extend(errs);all_bias[mode].extend(signed)
                error=(ys[mode][common]-truth[common])/scale*100
                no_drift=(ys[mode][common]-physio[common])/scale*100
                point_errors[mode].extend(error.tolist());no_drift_errors[mode].extend(no_drift.tolist())
                result=results[mode]
                analysis={'basis':'time' if mode=='time' else 'amplitude','amplitudeMode':'fixed',
                    'totalBins':10,'inhaleRising':True,'lower':lower,'upper':upper}
                record=compact_record_data(manager.build_record_data(FilterConfig(**result['filter_config']),
                    filtered_data=result['data'],peak_data=result['peak'],valley_data=result['valley'],
                    analysis=analysis,filter_status='offline',processing_quality=result['processingQuality']))
                binned=np.zeros(15000,dtype=bool)
                for b in record['respiratoryBins']:
                    assert START<=b['start']<b['end']<=STOP-1
                    assert not any(b['start']<iv['end'] and b['end']>iv['start'] for iv in record['processingQuality']['invalidIntervals'])
                    # Amplitude crossings are interpolated fractional sample positions.
                    binned[math.ceil(b['start']):math.ceil(b['end'])]=True
                assert not (binned & ~masks[mode]).any()
                per['modes'][mode]={'amplitude':summarize(errs),'signed_bias':float(np.mean(signed)) if signed else None,
                    'nrmse':float(np.sqrt(np.mean(error**2))) if len(error) else None,
                    'nrmse_no_drift':float(np.sqrt(np.mean(no_drift**2))) if len(no_drift) else None,
                    'valid_percent':float(masks[mode].sum()/30), 'binned_percent':float(binned.sum()/30),
                    'bin_intervals':len(record['respiratoryBins'])}
            pair=masks['time'] & masks['time20']
            same_cycles=[(a,b) for a,b in cycles if pair[a:b+1].all()]
            for key,mode in [('time5','time'),('time20','time20')]:
                context_errors[key].extend([100*abs(np.ptp(ys[mode][a:b+1])/np.ptp(truth[a:b+1])-1) for a,b in same_cycles])
            per['buffer_control_cycles']=len(same_cycles)
            if seed==42:
                # Reproducible illustration data, only synthetic records.
                np.savez_compressed('/private/tmp/respirascope-three-mode-measurement/'+sid+'.npz',
                    raw=np.asarray(raw),truth=truth,physio=physio,**{m:ys[m] for m in MODES})
            seed_rows.append(per)
        row={'id':sid,'name':name,'preset':asdict(cfg),'cough_seconds':cough_times,'seed_results':seed_rows,
            'paired_cycles':len(all_errors['time']),'possible_cycles':full_cycles*len(SEEDS),
            'contributing_seeds':sum(s['paired_cycles']>0 for s in seed_rows),
            'common_valid_seconds_mean':float(np.mean([s['common_valid_seconds'] for s in seed_rows])),
            'normalization_span':seed_rows[0]['normalization_span'],'modes':{},'buffer_control':{}}
        for mode in MODES:
            e=np.asarray(point_errors[mode]); nd=np.asarray(no_drift_errors[mode])
            row['modes'][mode]={'amplitude':summarize(all_errors[mode]),'signed_amplitude_bias':float(np.mean(all_bias[mode])) if all_bias[mode] else None,
                'nrmse':float(np.sqrt(np.mean(e**2))) if len(e) else None,
                'nrmse_no_drift':float(np.sqrt(np.mean(nd**2))) if len(nd) else None,
                'offset_percent':float(np.mean(e)) if len(e) else None,
                'valid_percent':float(np.mean([s['modes'][mode]['valid_percent'] for s in seed_rows])),
                'binned_percent':float(np.mean([s['modes'][mode]['binned_percent'] for s in seed_rows]))}
        row['buffer_control']={k:summarize(v) for k,v in context_errors.items()}
        rows.append(row)
        print(sid, 'cycles',row['paired_cycles'], 'amp',[round(row['modes'][m]['amplitude']['mean'],3) if row['modes'][m]['amplitude']['mean'] is not None else None for m in MODES],flush=True)
    sources=['scripts/measure_filter_amplitude.py','src/ct_breath/mock_sensor/breath_simulator.py',
        'src/ct_breath/breath_process/offline_quality.py','src/ct_breath/breath_process/peak_valley_detector.py',
        'src/ct_breath/breath_process/respiratory_bins.py','src/ct_breath/http/schemas.py','src/ct_breath/config.py']
    payload={'sampling_rate':FS,'seeds':SEEDS,'record_interval_seconds':[180,240],
        'raw_seconds':300,'filter_context_seconds_per_side':{'time':5,'amplitude':20,'baseline_lowpass':20},
        'mode_order':list(MODES),'truth':'Analytic simulator signal including configured slow baseline, before noise, artifacts, clipping and integer quantization.',
        'drift_free_truth':'Same analytic respiratory component and constant baseline, with known simulated slow drift removed. No drift is subtracted from filtered outputs.',
        'cycle_definition':'Underlying unmodulated oscillator valley-to-valley; full cycle inside record; clean peak-to-peak >5; entire cycle valid in every compared mode.',
        'metrics':'Mean and P95 of cycle absolute peak-to-peak relative error. Point NRMSE normalized by median drift-free truth cycle span in the full one-minute window. No time shifts, gain fits or baseline alignment. Common masks remove union of all invalid intervals.',
        'coverage':'Valid sample fraction and union of actual bin intervals / 3000 record samples, per mode, mean over seeds; no guarantee of correctness or CT completeness.',
        'source_sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},'results':rows}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False))
    print(OUT,flush=True)

if __name__=='__main__':main()

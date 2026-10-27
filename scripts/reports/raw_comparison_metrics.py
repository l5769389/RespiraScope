"""Descriptive processed-versus-observed metrics, not ground-truth accuracy."""
import numpy as np


def compare_to_raw(raw, filtered, valid, fs, nominal_bpm):
    raw=np.asarray(raw,dtype=float);filtered=np.asarray(filtered,dtype=float)
    valid=np.asarray(valid,dtype=bool)&np.isfinite(raw)&np.isfinite(filtered)
    if not valid.any():
        return {'valid_points':0,'mae_units':None,'mae_percent':None,
                'span_change_percent':None,'lag_ms':None,'correlation':None}
    x,y=raw[valid],filtered[valid]
    raw_span=float(np.percentile(x,95)-np.percentile(x,5))
    out={'valid_points':int(valid.sum()),'mae_units':float(np.mean(np.abs(y-x))),
         'mae_percent':float(np.mean(np.abs(y-x))/raw_span*100) if raw_span>0 else None,
         'span_change_percent':float(((np.percentile(y,95)-np.percentile(y,5))/raw_span-1)*100) if raw_span>0 else None,
         'lag_ms':None,'correlation':None}
    # Every lag uses the same raw anchors, with neither endpoint crossing a gap.
    # Two nominal respiratory periods must remain after the lag guard is removed.
    guard=int(round(.5*fs));minimum=int(np.ceil(2*60/nominal_bpm*fs))
    boundaries=np.diff(np.r_[False,valid,False].astype(int))
    regions=[(a+guard,b-guard) for a,b in zip(np.flatnonzero(boundaries==1),np.flatnonzero(boundaries==-1))
             if b-a>=minimum+2*guard]
    if not regions:return out
    scores=[]
    for lag in range(-guard,guard+1):
        numerator=xx=yy=0.
        for a,b in regions:
            u=raw[a:b];v=filtered[a+lag:b+lag]
            u=u-u.mean();v=v-v.mean()
            numerator+=float(u@v);xx+=float(u@u);yy+=float(v@v)
        corr=numerator/np.sqrt(xx*yy) if xx>0 and yy>0 else -np.inf
        scores.append((corr,-abs(lag),lag))
    corr,_,lag=max(scores)
    if np.isfinite(corr):out['correlation']=float(corr)
    # A search-edge maximum is censored; do not report it as a measured delay.
    if corr>=.5 and abs(lag)<guard:out['lag_ms']=float(lag*1000/fs)
    return out


def summarize_raw_comparison(samples):
    lags=[s['lag_ms'] for s in samples if s['lag_ms'] is not None]
    result={key:float(np.mean([s[key] for s in samples if s[key] is not None]))
            if any(s[key] is not None for s in samples) else None
            for key in ('mae_units','mae_percent','span_change_percent')}
    result.update(lag_ms_median=float(np.median(lags)) if lags else None,
                  lag_abs_ms_p95=float(np.percentile(np.abs(lags),95)) if lags else None,
                  lag_runs=len(lags),total_runs=len(samples))
    return result

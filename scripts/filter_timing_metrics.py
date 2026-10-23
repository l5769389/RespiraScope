"""Paired timing metrics for synthetic report data; does not alter detection."""
import numpy as np


def score_timing(truth, predictions, valid, fs, tolerance):
    """Match same-kind events one-to-one inside common valid regions.

    Erode both ends of every valid region by the matching tolerance so boundary
    censoring does not create spurious missing/extra events. A detected event
    outside the tolerance counts as unmatched, never as a small timing error.
    Only mutually matched, adjacent half breaths contribute internal bin edges.
    """
    tolerance=int(tolerance)
    valid=np.asarray(valid,dtype=bool)
    padded=np.pad((~valid).astype(int),(tolerance,tolerance),constant_values=1)
    prefix=np.r_[0,np.cumsum(padded)]
    width=2*tolerance+1
    interior=(prefix[width:]-prefix[:-width])==0
    eligible=lambda seq: 0<=seq<len(interior) and interior[seq]
    available=lambda seq: 0<=seq<len(valid) and valid[seq]
    maps={};summary={}
    for mode,events in predictions.items():
        mapping={};result={'reference':0,'predicted':0,'matched':0,'missed':0,'extra':0,
            'errors_ms':[],'peak_errors_ms':[],'valley_errors_ms':[],'boundary_errors_ms':[]}
        for kind in ('peak','valley'):
            # Match through the guard margin first. A correctly shifted event
            # entering the scoring interior must not become a false positive.
            expected=sorted(set(int(i) for i in truth[kind] if available(int(i))))
            detected=sorted(set(int(i) for i in events[kind] if available(int(i))))
            candidates=sorted((abs(a-b),a,b) for a in expected for b in detected
                if abs(a-b)<=tolerance and valid[min(a,b):max(a,b)+1].all())
            used_true=set();used_pred=set();pairs=[]
            for distance,a,b in candidates:
                if a in used_true or b in used_pred:continue
                used_true.add(a);used_pred.add(b);mapping[(a,kind)]=b;pairs.append((a,b))
            pairs=[(a,b) for a,b in pairs if eligible(a)]
            scored_expected=sum(bool(eligible(a)) for a in expected)
            extra=sum(bool(eligible(b) and b not in used_pred) for b in detected)
            errors=[abs(a-b)*1000/fs for a,b in sorted(pairs)]
            result[kind+'_errors_ms']=errors;result['errors_ms'].extend(errors)
            result['reference']+=scored_expected;result['predicted']+=len(pairs)+extra
            result['matched']+=len(pairs);result['missed']+=scored_expected-len(pairs);result['extra']+=extra
        maps[mode]=mapping;summary[mode]=result
    events=sorted((int(i),kind) for kind in ('peak','valley') for i in truth[kind])
    halves=0;candidate_halves=0
    for (a,ka),(b,kb) in zip(events,events[1:]):
        if ka==kb or not eligible(a) or not eligible(b) or not valid[a:b+1].all():continue
        candidate_halves+=1
        if not all((a,ka) in mapping and (b,kb) in mapping for mapping in maps.values()):continue
        adjacent=True
        for mode,mapping in maps.items():
            left,right=mapping[(a,ka)],mapping[(b,kb)]
            # An extra detected extremum between the endpoints changes the actual bins.
            if right<=left or any(left<int(i)<right for kind in ('peak','valley') for i in predictions[mode][kind]):
                adjacent=False;break
            if not valid[left:right+1].all():adjacent=False;break
        if not adjacent:continue
        halves+=1
        for mode,mapping in maps.items():
            left,right=mapping[(a,ka)],mapping[(b,kb)]
            for fraction in (.2,.4,.6,.8):
                actual=left+(right-left)*fraction;target=a+(b-a)*fraction
                summary[mode]['boundary_errors_ms'].append(abs(actual-target)*1000/fs)
    return {'modes':summary,'paired_half_breaths':halves,'candidate_half_breaths':candidate_halves,
        'matching_tolerance_samples':tolerance,'common_interior_seconds':float(interior.sum()/fs)}

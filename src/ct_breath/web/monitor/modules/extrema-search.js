import {validSequence} from './record-quality.js';

// This is a local editing aid, not a replacement for automatic detection.
// Use the local sample spacing and available support, without a prominence
// threshold: a person is selecting the turn, rather than detecting all breaths.
function localRun(points, sequence, {samplingRate=50,gap=25,invalidIntervals=[],radiusSeconds=1}={}) {
  if (!points.length || !Number.isFinite(sequence)) return null;
  const radius=Math.max(3,samplingRate*radiusSeconds), flank=Math.max(3,Math.round(samplingRate*.12));
  let lo=0,hi=points.length;
  while(lo<hi){const mid=(lo+hi)>>1;if(points[mid][0]<sequence)lo=mid+1;else hi=mid;}
  const steps=[];
  for(let i=Math.max(1,lo-16);i<Math.min(points.length,lo+17);i++) {
    const step=points[i][0]-points[i-1][0];
    if(step>0 && step<=gap)steps.push(step);
  }
  steps.sort((a,b)=>a-b);
  const step=steps.length?steps[Math.floor((steps.length-1)/2)]:1;
  gap=Math.min(gap,step*1.5);
  if(lo && lo<points.length && sequence>points[lo-1][0] && sequence<points[lo][0] && points[lo][0]-points[lo-1][0]>gap) return null;
  const center=lo===points.length?lo-1:lo>0 && sequence-points[lo-1][0]<points[lo][0]-sequence?lo-1:lo;
  const valid=i=>Number.isFinite(points[i][1]) && validSequence(points[i][0],invalidIntervals);
  const linked=(a,b)=>points[b][0]-points[a][0]<=gap &&
    !invalidIntervals.some(r=>r.start<points[b][0] && r.end>points[a][0]);
  if(!valid(center) || Math.abs(points[center][0]-sequence)>radius) return null;
  let start=center,end=center;
  while(start>0 && linked(start-1,start) && valid(start-1) && sequence-points[start-1][0]<=radius+flank*step) start--;
  while(end+1<points.length && linked(end,end+1) && valid(end+1) && points[end+1][0]-sequence<=radius+flank*step) end++;
  const values=points.slice(start,end+1).map(p=>p[1]);
  const span=Math.max(...values)-Math.min(...values);
  const epsilon=Math.max(1e-12,span*1e-10);
  return {start,end,center,radius,flank,epsilon};
}

export function findNearbyExtremum(points,sequence,options={}) {
  const run=localRun(points,sequence,options);
  if(!run)return null;
  const {start,end,radius,flank,epsilon}=run;
  const candidates=[];
  for(let i=start+1;i<end;i++) {
    let last=i;
    while(last<end && Math.abs(points[last+1][1]-points[i][1])<=epsilon)last++;
    const index=Math.floor((i+last)/2),point=points[index];
    if(last<end && Math.abs(point[0]-sequence)<=radius) {
      const left=point[1]-points[i-1][1],right=point[1]-points[last+1][1];
      const sign=left>epsilon && right>epsilon?1:left< -epsilon && right< -epsilon?-1:0;
      const leftSupport=Math.max(start,i-flank),rightSupport=Math.min(end,last+flank);
      const prominence=Math.min(sign*(point[1]-points[leftSupport][1]),sign*(point[1]-points[rightSupport][1]));
      if(sign && prominence>epsilon) candidates.push({key:sign>0?'peaks':'valleys',point:point.slice(0,2)});
    }
    i=last;
  }
  candidates.sort((a,b)=>Math.abs(a.point[0]-sequence)-Math.abs(b.point[0]-sequence));
  return candidates[0] ?? null;
}

// Exact entry preserves the requested sample; only its marker type is inferred.
export function inferExtremumType(points,sequence,options={}) {
  const run=localRun(points,sequence,options);
  if(!run)return null;
  const {center,epsilon}=run;
  const start=Math.max(run.start,center-run.flank),end=Math.min(run.end,center+run.flank);
  const p=points[center][1],left=points[start][1],right=points[end][1];
  if(center===start && center<end)return p-right>epsilon?'peaks':right-p>epsilon?'valleys':null;
  if(center===end && center>start)return p-left>epsilon?'peaks':left-p>epsilon?'valleys':null;
  if(start===end)return null;
  const fraction=(points[center][0]-points[start][0])/(points[end][0]-points[start][0]);
  const curvature=p-(left+(right-left)*fraction);
  if(Math.abs(curvature)>epsilon)return curvature>0?'peaks':'valleys';
  return findNearbyExtremum(points,sequence,options)?.key ?? null;
}

// Keep in sync with ct_breath/binning/segments.py. These helpers neither
// synthesize samples nor change the public peak/valley annotations.
function* continuousRuns(data, invalid, gap) {
  let current = [];
  for (const point of data) {
    const [x,y] = point;
    if (!Number.isFinite(x) || !Number.isFinite(y) || invalid.some(i=>i.start<=x && x<i.end)) {
      if (current.length) { yield current; current=[]; }
      continue;
    }
    if (current.length && (!(x>current.at(-1)[0] && x-current.at(-1)[0]<=gap) ||
        invalid.some(i=>current.at(-1)[0]<i.end && x>=i.start))) {
      yield current; current=[];
    }
    current.push(point);
  }
  if (current.length) yield current;
}

function clearLeg(points, threshold, minSpan) {
  if (points.length<3 || Math.abs(points.at(-1)[0]-points[0][0])<minSpan) return false;
  const distance=Math.abs(points.at(-1)[1]-points[0][1]);
  let variation=0;
  for(let i=1;i<points.length;i++) variation+=Math.abs(points[i][1]-points[i-1][1]);
  return distance>=threshold && distance>=.9*variation;
}

function consistentDirection(points, rising, threshold) {
  // Missing pairs of turns must not turn a whole breath into one direction.
  const sign=rising?1:-1;
  let best=sign*points[0][1];
  for(let i=1;i<points.length;i++) {
    const value=sign*points[i][1];
    best=Math.max(best,value);
    if(best-value>=threshold) return false;
  }
  return true;
}

function missingTurn(points, left, right, kind, threshold, minSpan) {
  const values=points.slice(left,right+1).map(p=>p[1]);
  const target=values.reduce((a,b)=>kind==='peak'?Math.min(a,b):Math.max(a,b));
  const hits=values.flatMap((y,i)=>y===target?[left+i]:[]);
  const first=hits[0], last=hits.at(-1);
  if(first===left || last===right || last-first+1!==hits.length || points[last][0]-points[first][0]>minSpan) return null;
  const index=Math.floor((first+last)/2);
  return clearLeg(points.slice(left,index+1),threshold,minSpan) && clearLeg(points.slice(index,right+1),threshold,minSpan) ? index : null;
}

function edgeLeg(points, index, step, kind, threshold, minSpan) {
  const sign=kind==='peak'?-1:1;
  let best=index;
  for(let j=index+step;j>=0 && j<points.length;j+=step) {
    if(sign*(points[j][1]-points[best][1])>0) best=j;
    else if(sign*(points[best][1]-points[j][1])>=threshold) break;
  }
  const segment=points.slice(Math.min(index,best),Math.max(index,best)+1);
  return clearLeg(segment,threshold,minSpan)?segment:null;
}

export function* binningSegments(data, events, invalid, gap, fixed, samplingRate) {
  for(const points of continuousRuns(data,invalid,gap)) {
    const lookup=new Map(points.map((p,i)=>[p[0],i]));
    const anchors=events.filter(([x])=>lookup.has(x)).map(([x,kind])=>[lookup.get(x),kind]);
    if(!anchors.length) continue;
    const values=points.map(p=>p[1]).sort((a,b)=>a-b);
    const span=values[Math.floor((values.length-1)*.95)]-values[Math.floor((values.length-1)*.05)];
    const threshold=Math.max(1,.1*span), minSpan=Math.max(1,.2*samplingRate), recovered=[];
    for(let i=0;i<anchors.length-1;i++) {
      const [a,kind]=anchors[i], [b,nextKind]=anchors[i+1];
      recovered.push([a,kind]);
      if(kind===nextKind && b>a) {
        const turn=missingTurn(points,a,b,kind,threshold,minSpan);
        if(turn!==null) recovered.push([turn,kind==='peak'?'valley':'peak']);
      }
    }
    recovered.push(anchors.at(-1));
    if(fixed) {
      const [a,kind]=recovered[0];
      const segment=edgeLeg(points,a,-1,kind,threshold,minSpan);
      if(segment) yield [segment,kind==='peak'];
    }
    for(let i=0;i<recovered.length-1;i++) {
      const [a,kind]=recovered[i], [b,nextKind]=recovered[i+1];
      if(kind===nextKind || b<=a) continue;
      const rising=kind==='valley';
      const segment=points.slice(a,b+1);
      if(points[b][1]!==points[a][1] && (points[b][1]>points[a][1])===rising &&
          consistentDirection(segment,rising,threshold)) yield [segment,rising];
    }
    if(fixed) {
      const [a,kind]=recovered.at(-1);
      const segment=edgeLeg(points,a,1,kind,threshold,minSpan);
      if(segment) yield [segment,kind==='valley'];
    }
  }
}

// Same schema and classification precedence as ct_breath/binning/data.py.
export function buildBinningTimeline(filtered, bins, invalid, options, start, end, fs=50, gap=25) {
  const fixed=options.basis==='amplitude' && options.amplitudeMode==='fixed';
  const result={version:3,coordinate:'sample_sequence',intervalConvention:'[start,end)',
    range:[start,end],samplingRateHz:fs,method:(options.basis??'time')==='time'?'time':fixed?'amplitude-fixed':'amplitude-free',
    totalBins:options.totalBins??10,inhaleRising:options.inhaleRising??true,intervals:[]};
  if(fixed) {
    if(![options.lower,options.upper].every(Number.isFinite)||options.lower>=options.upper)
      throw new Error('Fixed amplitude binning requires finite lower < upper bounds');
    result.amplitudeBounds=[options.lower,options.upper];
  }
  if(!Number.isFinite(start)||!Number.isFinite(end)||end<=start) return result;
  const events=new Map([[start,[]],[end,[]]]);
  let identifier=0;
  function add(a,b,kind,value=null) {
    a=Math.max(a,start);b=Math.min(b,end);
    if(b<=a)return;
    const id=++identifier;
    if(!events.has(a))events.set(a,[]);
    if(!events.has(b))events.set(b,[]);
    events.get(a).push([id,[kind,value]]);events.get(b).push([id,null]);
  }
  for(const item of bins) add(item.start,item.end,'bin',[item.direction,item.bin]);
  for(const item of invalid) add(item.start,item.end,'quality');
  const points=filtered.map(p=>Array.isArray(p)?p:[p.sequence,p.value]);
  if(fixed) for(let i=0;i<points.length;i++) {
    const [x,y]=points[i];
    if(![x,y].every(Number.isFinite)||(options.lower<=y&&y<=options.upper))continue;
    // Sample ownership preserves inclusive bounds; do not bridge acquisition gaps.
    const following=points[i+1]?.[0]??x+1;
    const stop=Number.isFinite(following)&&following-x>0&&following-x<=gap?following:x+1;
    add(x,stop,'range');
  }
  for(let i=1;i<points.length;i++) {
    const [x0,y0]=points[i-1],[x1,y1]=points[i];
    if(![x0,y0,x1,y1].every(Number.isFinite)||!(x1-x0>0&&x1-x0<=gap))continue;
    add(x0,x1,'available');
  }
  const active=new Map(),positions=[...events.keys()].sort((a,b)=>a-b);
  for(let i=1;i<positions.length;i++){
    const a=positions[i-1],b=positions[i];
    for(const [key,value] of events.get(a)){if(value===null)active.delete(key);else active.set(key,value);}
    const groups={quality:[],range:[],available:[],bin:[]};
    for(const [kind,value] of active.values())groups[kind].push(value);
    let status='unassigned',direction=null,number=null;
    if(groups.quality.length||groups.range.length)status='excluded';
    else if(groups.available.length&&groups.bin.length){status='valid';[direction,number]=groups.bin[0];}
    const item={start:a,end:b,status,direction,bin:number},previous=result.intervals.at(-1);
    if(status==='excluded')item.exclusion=groups.quality.length?'quality':'range';
    if(previous&&previous.end===a&&['status','direction','bin','exclusion'].every(k=>previous[k]===item[k]))previous.end=b;
    else result.intervals.push(item);
  }
  return result;
}

export function compactBinningData(filtered,timeline) {
  const groups=Object.fromEntries(['inhale','exhale'].map(direction=>[direction,Array.from({length:timeline.totalBins/2},()=>[])]));
  const result={version:5,inhaleRising:timeline.inhaleRising,bins:groups,excluded:{quality:[],range:[]},unassigned:[]};
  const sequences=filtered.map(p=>Array.isArray(p)?p[0]:p.sequence);
  function index(value){let lo=0,hi=sequences.length;while(lo<hi){const mid=(lo+hi)>>>1;if(sequences[mid]<value)lo=mid+1;else hi=mid;}return lo;}
  function append(group,a,b){if(group.at(-1)?.[1]===a)group.at(-1)[1]=b;else group.push([a,b]);}
  for(const row of timeline.intervals){
    const a=index(row.start),b=index(row.end);if(b<=a)continue;
    if(row.status==='valid')append(groups[row.direction][row.bin-1],a,b);
    else if(row.status==='excluded')append(result.excluded[row.exclusion],a,b);
    else append(result.unassigned,a,b);
  }
  return result;
}

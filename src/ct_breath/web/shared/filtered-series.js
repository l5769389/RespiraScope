// Styling never changes filtered values or data used for binning/export.
export function withSequenceGaps(points, gap=25) {
  const result=[];
  for (const point of points) {
    const previous=result.at(-1);
    if (previous && point[0]-previous[0]>gap) result.push([previous[0]+1,null]);
    result.push(point);
  }
  return result;
}

export function splitFilteredSeries(points, quality, gap=25) {
  const data=withSequenceGaps(points,gap);
  const intervals=quality?.invalidIntervals ?? [];
  const excluded=data.map(([x])=>intervals.some(i=>x>=i.start && x<i.end));
  const filtered=data.map((p,i)=>excluded[i]?[p[0],null]:p);
  // v1 stored raw placeholders inside artifacts. Never draw those as filtered.
  if (quality?.version!==2) return {filtered,reference:[]};
  const reference=data.map((p,i)=>excluded[i]?p:[p[0],null]);
  for(let i=1;i<data.length;i++) {
    if(!Number.isFinite(data[i-1][1]) || !Number.isFinite(data[i][1])) continue;
    if(excluded[i]!==excluded[i-1]) {
      // The edge touching an excluded sample is dashed. Both series meet at
      // the same measured endpoint; no interpolation or value replacement.
      reference[i-1]=data[i-1];
      reference[i]=data[i];
    }
  }
  return {filtered,reference};
}

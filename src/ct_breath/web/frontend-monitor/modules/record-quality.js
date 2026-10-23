const reasons = new Set(['spike','motion','filter_edge','gap','too_short']);
const statuses = new Set(['estimated','insufficient_cycles','disabled','preserved']);
const rangeOK = item => item && Number.isFinite(item.start) && Number.isFinite(item.end) && item.start >= 0 && item.end > item.start;

// Legacy files may omit quality. Malformed masks must never silently become
// empty masks: that would turn uncertain samples into valid reconstruction bins.
export function normalizeQuality(value) {
  if (value == null) return undefined;
  if (![1,2].includes(value.version) || !Array.isArray(value.invalidIntervals) || !Array.isArray(value.baselines)
      || value.invalidIntervals.some(i=>!rangeOK(i) || !reasons.has(i.reason))
      || value.baselines.some(i=>!rangeOK(i) || !statuses.has(i.status)
        || !Number.isInteger(i.cycles) || i.cycles < 0 || (i.offset != null && !Number.isFinite(i.offset)))) {
    throw new Error('无效的离线质量信息 / Invalid offline quality metadata');
  }
  return {version:value.version,
    invalidIntervals:value.invalidIntervals.map(({start,end,reason})=>({start,end,reason})),
    baselines:value.baselines.map(({start,end,status,cycles,offset})=>({start,end,status,cycles,...(offset != null ? {offset} : {})})),
  };
}

export function mergeQuality(results) {
  const items = results.map(r=>normalizeQuality(r.processingQuality)).filter(Boolean);
  return items.length ? {version:Math.min(...items.map(q=>q.version)),invalidIntervals:items.flatMap(q=>q.invalidIntervals),baselines:items.flatMap(q=>q.baselines)} : undefined;
}

export const invalidIntervals = source => source.processingQuality?.invalidIntervals ?? [];
export const validSequence = (sequence, intervals) => !intervals.some(i=>sequence >= i.start && sequence < i.end);

export function validExtrema(points, source) {
  const intervals = invalidIntervals(source);
  return points.filter(p=>validSequence(Array.isArray(p) ? p[0] : p.sequence, intervals));
}

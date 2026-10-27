import {invalidIntervals, validSequence} from './record-quality.js';
import {binningSegments} from './binning-segments.js';
export const BIN_COUNTS = [4,6,8,10,12,16,20];
export const normalizeBinCount = value => BIN_COUNTS.includes(value) ? value : 10;

// Sequence coordinates are retained (including fractional crossing positions).
// Time/free bins require measured endpoints; fixed bins can retain anchored tails.
export function buildRespiratoryBins(source, options = {}) {
  const count = normalizeBinCount(options.totalBins)/2;
  const { basis = 'time', amplitudeMode = 'free', lower, upper,
    inhaleRising = true, gap = 25 } = options;
  if (basis === 'amplitude' && amplitudeMode === 'fixed' &&
      (!Number.isFinite(lower) || !Number.isFinite(upper) || lower >= upper)) return [];
  const point = p => Array.isArray(p) ? p : [p.sequence, p.value];
  const data = (source.filtered ?? []).map(point);
  const events = [
    ...(source.peaks ?? []).map(p => [point(p)[0],'peak']),
    ...(source.valleys ?? []).map(p => [point(p)[0],'valley']),
  ].sort((a,b) => a[0]-b[0]);
  const bins = [];
  const invalid = invalidIntervals(source);
  const fixed = basis === 'amplitude' && amplitudeMode === 'fixed';
  const samplingRate = source.filterConfig?.sampling_rate ?? 50;
  for (const [segment,rising] of binningSegments(data,events,invalid,gap,fixed,samplingRate)) {
    const start=segment[0][0], end=segment.at(-1)[0];
    const direction = rising === inhaleRising ? 'inhale' : 'exhale';
    if (basis === 'time') {
      for (let bin = 1; bin <= count; bin++) bins.push({
        start:start+(end-start)*(bin-1)/count, end:start+(end-start)*bin/count, direction, bin,
      });
      continue;
    }
    const lo = amplitudeMode === 'fixed' ? lower : Math.min(segment[0][1],segment.at(-1)[1]);
    const hi = amplitudeMode === 'fixed' ? upper : Math.max(segment[0][1],segment.at(-1)[1]);
    const levels = Array.from({length:count+1}, (_,i) => lo+(hi-lo)*i/count);
    let previous = null;
    for (let i = 0; i < segment.length-1; i++) {
      const [x0,y0] = segment[i], [x1,y1] = segment[i+1];
      const fractions = [0,1];
      if (y1 !== y0) for (const level of levels) {
        const f = (level-y0)/(y1-y0);
        if (f > 0 && f < 1) fractions.push(f);
      }
      fractions.sort((a,b)=>a-b);
      for (let j = 0; j < fractions.length-1; j++) {
        const f0 = fractions[j], f1 = fractions[j+1];
        const value = y0+(y1-y0)*(f0+f1)/2;
        if (value < lo || value > hi) { previous = null; continue; }
        const band = Math.min(count-1, Math.floor((value-lo)/(hi-lo)*count));
        const bin = rising ? band+1 : count-band;
        const left = x0+(x1-x0)*f0, right = x0+(x1-x0)*f1;
        if (right <= left) continue;
        if (previous && previous.bin === bin && Math.abs(previous.end-left) < 1e-7) previous.end = right;
        else {
          previous = {start:left, end:right, direction, bin};
          bins.push(previous);
        }
      }
    }
  }
  return bins;
}

export function defaultAmplitudeBounds(source) {
  const invalid = invalidIntervals(source);
  // Context improves filtering, but must not set bounds for another interval.
  const values = (source.filtered ?? []).filter(p=>
    (!Number.isFinite(source.startSeq) || p[0] >= source.startSeq) &&
    (!Number.isFinite(source.endSeq) || p[0] <= source.endSeq) && validSequence(p[0],invalid))
    .map(p=>Number(p[1])).filter(Number.isFinite).sort((a,b)=>a-b);
  if (!values.length) return {lower:0,upper:100};
  const lower = values[Math.floor((values.length-1)*0.05)];
  const upper = values[Math.floor((values.length-1)*0.95)];
  return {lower, upper:Math.max(lower+0.1,upper)};
}

export function extremumRange(value, options = {}) {
  if (options.basis !== 'amplitude' || options.amplitudeMode !== 'fixed' ||
      !Number.isFinite(options.lower) || !Number.isFinite(options.upper) || options.upper <= options.lower) return 'not_applicable';
  return value < options.lower ? 'below' : value > options.upper ? 'above' : 'inside';
}

export function annotateExtremum(point, options) {
  const amplitudeRange = extremumRange(point.value, options);
  return {...point, amplitudeRange,
    outOfRange: amplitudeRange === 'not_applicable' ? null : amplitudeRange !== 'inside'};
}

// Always describe all configured direction/bin combinations; absent data stays empty.
export function buildBinningMetadata(options, intervals) {
  const count = normalizeBinCount(options.totalBins)/2;
  const fixed = options.basis === 'amplitude' && options.amplitudeMode === 'fixed';
  const amplitudeEdges = fixed ? Array.from({length:count+1},(_,i)=>options.lower+(options.upper-options.lower)*i/count) : null;
  const groups = [];
  for (const direction of ['inhale','exhale']) for (let bin=1;bin<=count;bin++) {
    const rising = (direction === 'inhale') === (options.inhaleRising !== false);
    const amplitudeBand = fixed ? (rising ? bin : count+1-bin) : null;
    groups.push({direction,bin,amplitudeBand,
      amplitudeLower:fixed ? amplitudeEdges[amplitudeBand-1] : null,
      amplitudeUpper:fixed ? amplitudeEdges[amplitudeBand] : null,
      intervals:intervals.filter(b=>b.direction === direction && b.bin === bin).map(b=>({start:b.start,end:b.end})),
    });
  }
  return {version:1,basis:options.basis,amplitudeMode:options.basis === 'amplitude' ? options.amplitudeMode : null,
    binsPerDirection:count,totalBins:count*2,inhaleRising:options.inhaleRising !== false,
    amplitudeBounds:fixed ? {lower:options.lower,upper:options.upper} : null,
    amplitudeEdges,intervalConvention:'[start,end)',groups};
}

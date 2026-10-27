import { buildRespiratoryBins, defaultAmplitudeBounds, normalizeBinCount } from './respiratory-bins.js';
import {mergeQuality,invalidIntervals} from './record-quality.js';
import {buildBinningTimeline,compactBinningData} from './binning-data.js';
import {createExtremaEditor} from './extrema-editor.js';
import {createBinningDetails} from './binning-details.js';

export function createRecordAnalysis(ctx) {
  const {state, apiFetch, normalizeSeries, buildFilterConfig, buildOfflineFilterConfig, chartApi, getCurrentLanguage} = ctx;
  const el = Object.fromEntries(['filterHint','bandHighLabel','totalBins','basis','amplitudeMode','lower','upper','direction','bounds','amplitude','status','retry','bandHigh','sensitivity','reset','bandHighValue','bandHighBpm','bandTrack','discard','state']
    .map(key=>[key,document.querySelector(`#analysis-${key}`)]));
  let busy = false;
  let draft = null;
  let failure = null;
  let progress = null;
  const binCache = new WeakMap();
  const details = createBinningDetails({getData:()=>data(),getTimeline:()=>timeline(),getCurrentLanguage});
  const editor = createExtremaEditor({state,chartApi,getCurrentLanguage,unavailable:()=>isBusy() || hasPendingChanges(),onChange:refreshExtrema});
  const sensitivityValue = config => config.auto_peak_detection !== false && [0.45,0.3,0.15].includes(config.peak_threshold_ratio ?? 0.3)
    ? String(config.peak_threshold_ratio ?? 0.3) : 'keep';
  function resetDraft(record) {
    failure = null;
    const config = buildOfflineFilterConfig(record.filterConfig ?? {});
    draft = {record, source:record.filterConfig, high:String(config.highpass_cutoff),
      sensitivity:sensitivityValue(config), preset:false, edited:false};
  }
  // Logarithmic positions give the low respiratory frequencies useful travel,
  // while retaining the backend's full supported frequency range.
  function maximumHz() {
    const fs = state.lastRecord?.filterConfig?.sampling_rate ?? 50;
    return Math.min(20, (Math.ceil(fs / 2 * 1000) - 1) / 1000);
  }
  function syncBandSliders() {
    const maximum = maximumHz();
    el.bandHighLabel.textContent = zh() ? '低通上限频率' : 'Low-pass cutoff';
    for (const [key,field] of [['bandHigh','high']]) {
      const hz = Number(draft[field]);
      const position = Math.max(0,Math.min(1000,1000*Math.log(hz/.01)/Math.log(maximum/.01)));
      el[key].value = String(position);
      el[key].dataset.maxHz = String(maximum);
      el[key].dataset.hz = String(hz);
      el.bandTrack.style.setProperty(`--${field}-progress`,`${position/10}%`);
      const label = `${hz.toFixed(2)} Hz`;
      el[`${key}Value`].textContent = label;
      const bpm = `${(hz*60).toFixed(2)} BPM`;
      el[`${key}Bpm`].textContent = bpm;
      el[key].setAttribute('aria-valuetext',`${label}, ${bpm}`);
    }
  }
  function hasPendingChanges() {
    const record = state.lastRecord;
    if (!record || draft?.record !== record || draft.source !== record.filterConfig) return false;
    if (!draft.edited) return false;
    const config = record.filterConfig ?? buildFilterConfig();
    return config.offline_filter !== 'baseline_lowpass' || draft.high.trim() === ''
      || Number(draft.high) !== config.highpass_cutoff || draft.sensitivity !== sensitivityValue(config)
      || (draft.preset && config.bandpass_mode === 'custom');
  }
  const isBusy = () => busy || Boolean(state.lastRecord?.analysisPending);
  const zh = () => getCurrentLanguage() === 'zh';
  function settings(record = state.lastRecord) {
    if (!record) return null;
    record.analysis ??= {basis:record.filterConfig?.processing_mode ?? 'time', amplitudeMode:'free', inhaleRising:true};
    record.analysis.totalBins = normalizeBinCount(record.analysis.totalBins);
    if (!Number.isFinite(record.analysis.lower) || !Number.isFinite(record.analysis.upper)) {
      const bounds = defaultAmplitudeBounds(record);
      // A recording still being finalized contains a temporary realtime curve.
      // Only persist automatic bounds after offline data and quality are ready.
      if (record.analysisPending) return {...record.analysis, ...bounds};
      Object.assign(record.analysis, bounds);
    }
    return record.analysis;
  }
  function bins(record = state.lastRecord) {
    if (!record || record.analysisPending) return [];
    const options = {...settings(record), gap:record.filterConfig?.data_gap_reset_points ?? 25};
    const signature = JSON.stringify([options,record.startSeq,record.endSeq,record.filtered.length,record.peaks.length,record.valleys.length,invalidIntervals(record)]);
    const cached = binCache.get(record);
    if (cached?.signature === signature && cached.filtered === record.filtered && cached.peaks === record.peaks && cached.valleys === record.valleys) return cached.value;
    const value = buildRespiratoryBins(record, options)
      .map(bin=>({...bin,start:Math.max(bin.start,record.startSeq),end:Math.min(bin.end,record.endSeq)}))
      .filter(bin=>bin.end>bin.start);
    binCache.set(record,{signature,filtered:record.filtered,peaks:record.peaks,valleys:record.valleys,value});
    return value;
  }
  function timeline(record = state.lastRecord) {
    if (!record || record.analysisPending) return null;
    return buildBinningTimeline(record.filtered, bins(record), invalidIntervals(record), settings(record),
      record.startSeq, record.endSeq, record.filterConfig?.sampling_rate ?? 50,
      record.filterConfig?.data_gap_reset_points ?? 25);
  }
  function data(record = state.lastRecord) {
    const value=timeline(record);
    return value ? compactBinningData(record.filtered,value) : null;
  }
  function sync() {
    const record = state.lastRecord, options = settings(record);
    editor.sync();
    details.sync(!record || isBusy() || hasPendingChanges() || editor.isEditing());
    if (!options) return;
    if (draft?.record !== record || draft.source !== record.filterConfig) resetDraft(record);
    ctx.recordApi?.updateRecordButtons();
    syncBandSliders();
    const legacy = record.filterConfig?.offline_filter !== 'baseline_lowpass';
    el.filterHint.textContent = legacy ? (zh() ? '当前为旧版结果；这里的低通设置将在重新计算后生效。' : 'Showing a legacy result; these low-pass settings apply on recalculation.') : zh()
      ? '共用双向低通；切换分箱不改变曲线。更改上限需重新计算；灵敏度仅重判峰谷。'
      : 'Shared forward-backward low-pass; binning changes keep the same curve. Apply cutoff edits to re-filter; sensitivity only re-detects extrema.';
    el.sensitivity.value = draft.sensitivity;
    el.sensitivity.querySelector('[value="keep"]').hidden = sensitivityValue(record.filterConfig ?? {}) !== 'keep';
    el.totalBins.value = String(options.totalBins);
    el.basis.value = options.basis;
    el.amplitudeMode.value = options.amplitudeMode;
    el.direction.value = options.inhaleRising ? 'rising' : 'falling';
    el.lower.value = options.lower.toFixed(2);
    el.upper.value = options.upper.toFixed(2);
    el.amplitude.hidden = options.basis !== 'amplitude';
    el.bounds.hidden = options.basis !== 'amplitude' || options.amplitudeMode !== 'fixed';
    for (const key of ['totalBins','basis','amplitudeMode','lower','upper','direction','retry','bandHigh','sensitivity','reset']) el[key].disabled = isBusy() || editor.isEditing();
    // Binning uses the applied curve; pending filter edits do not change it.
    el.basis.disabled = isBusy() || editor.isEditing();
    const hz = value => value.toFixed(2);
    const basisName = options.basis === 'time' ? (zh()?'时间分箱':'Time binning') : (zh()?'幅值分箱':'Amplitude binning');
    const band = record.filterConfig?.offline_filter === 'baseline_lowpass'
      ? `${zh()?'保留基线低通':'Baseline-preserving low-pass'} ≤ ${hz(record.filterConfig.highpass_cutoff)} Hz`
      : `${zh()?'带通滤波':'Band-pass filter'} ${hz(record.filterConfig?.lowpass_cutoff ?? 0.1)}–${hz(record.filterConfig?.highpass_cutoff ?? 40/60)} Hz`;
    const count = bins(record).length;
    const boundaryHint = options.basis === 'amplitude' && options.amplitudeMode === 'fixed'
      ? (zh()?'横向虚线等分幅值；实线为可拖动上下限':'Horizontal dashed lines divide amplitude; drag the solid bounds')
      : (zh()?'纵向虚线为分箱边界，放大查看吸／呼编号':'Vertical dashed boundaries; zoom in for bin labels');
    el.status.textContent = failure ? `${zh()?'重算失败，保留原结果':'Re-filter failed; previous result retained'}: ${failure}` : record.analysisPending ? (zh()?'正在完成记录和首次滤波，请稍候…':'Finishing capture and initial filtering…') : busy ? (progress ?? (zh()?'正在更新离线分析…':'Updating offline analysis…')) : hasPendingChanges() ? (zh()?'设置尚未应用：点击“应用设置”后更新波形、峰谷及分箱。':'Settings pending: apply to update the curve, extrema and bins.') :
      `${record.filterConfig?.offline_filter !== 'baseline_lowpass' ? (zh()?'旧版结果；重新计算将使用低通。':'Legacy result; recalculation will use low-pass. ') : ''}${basisName} · ${band} · ${zh()?`吸气 ${options.totalBins/2} 箱 / 呼气 ${options.totalBins/2} 箱`:`${options.totalBins/2} inhale / ${options.totalBins/2} exhale bins`} · ${count ? boundaryHint : (zh()?'暂无可分箱的完整呼吸段':'No bounded breath segments')}`;
    el.status.toggleAttribute('data-error',Boolean(failure));
    el.status.toggleAttribute('data-pending',hasPendingChanges() && !isBusy());
    const phase = isBusy() ? 'busy' : editor.isEditing() ? 'editing' : failure ? 'error' : hasPendingChanges() ? 'pending' : legacy ? 'legacy' : 'applied';
    el.state.dataset.state = phase;
    el.state.textContent = (zh() ? {editing:'分箱预览',busy:'处理中',error:'应用失败',pending:'待应用',applied:'已应用',legacy:'旧版结果'} : {editing:'Binning preview',busy:'Processing',error:'Failed',pending:'Pending',applied:'Applied',legacy:'Legacy result'})[phase];
    el.retry.textContent = isBusy() ? (zh()?'处理中…':'Processing…') : hasPendingChanges() ? (zh()?'应用设置':'Apply settings') : legacy ? (zh()?'使用低通重算':'Recalculate low-pass') : (zh()?'重新计算':'Recalculate');
    el.retry.setAttribute('aria-busy',String(isBusy()));
    el.discard.hidden = !hasPendingChanges();
    el.discard.disabled = isBusy();
  }
  function refreshExtrema() { sync(); chartApi.updateRecordEditing(); }
  function redraw() { sync(); chartApi.renderRecord({preserveZoom:true}); }
  function updateBound(key,value,{preview=false} = {}) {
    if (isBusy() || editor.isEditing() || !Number.isFinite(value)) return;
    const options = settings();
    if (!options) return;
    // Keep a nonzero interval even when handles approach each other.
    options[key] = key === 'lower' ? Math.min(value,options.upper-0.01) : Math.max(value,options.lower+0.01);
    el[key].value = options[key].toFixed(2);
    if (preview) chartApi.updateRecordBins();
    else redraw();
  }
  async function refilter(nextBasis, {useDraft=false} = {}) {
    if (isBusy() || editor.isEditing() || !state.lastRecord) return;
    const record = state.lastRecord;
    const oldOptions = {...settings(record)};
    const filterConfig = buildOfflineFilterConfig({...record.filterConfig,processing_mode:nextBasis});
    let detectionOnly = false;
    if (useDraft) {
      const high = Number(draft.high);
      const methodChanged = record.filterConfig?.offline_filter !== 'baseline_lowpass';
      if (!draft.high.trim() || !Number.isFinite(high) || high < .01 || high > maximumHz()) {
        el.status.textContent = zh() ? '请输入有效的低通上限，且小于采样率的一半。' : 'Choose a valid cutoff below half the sampling rate.';
        el.status.dataset.error = 'true';
        return;
      }
      const bandChanged = methodChanged || high !== record.filterConfig?.highpass_cutoff;
      filterConfig.highpass_cutoff = high;
      filterConfig.bandpass_mode = 'custom';
      if (draft.sensitivity !== 'keep') {
        filterConfig.auto_peak_detection = true;
        filterConfig.peak_threshold_ratio = Number(draft.sensitivity);
      }
      detectionOnly = !bandChanged && hasPendingChanges();
    }
    failure = null;
    progress = null;
    busy = true;
    sync();
    try {
      let results;
      if (detectionOnly) {
        if (!record.filtered.length) throw new Error(zh()?'暂无滤波数据，请先重新滤波':'No filtered data available');
        const response = await apiFetch('/detectPeaks', {
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({filter_config:filterConfig,filtered_data:record.filtered,invalid_intervals:invalidIntervals(record)}),
        });
        if (!response.ok) throw new Error(await window.RespiraScopeShared.responseError(response));
        results = [await response.json()];
      } else {
        const segments = [];
        for (const point of record.raw) {
          const current = segments.at(-1);
          if (!current || point[0]-current.at(-1)[0] > (filterConfig.data_gap_reset_points ?? 25)) segments.push([point]);
          else current.push(point);
        }
        const usable = segments.filter(segment=>segment.length>=300);
        if (!usable.length) throw new Error(zh()?'原始数据不足，无法重新滤波':'Not enough raw data to re-filter');
        results = [];
        for (const [index,segment] of usable.entries()) {
          progress = zh() ? `正在滤波 ${index+1} / ${usable.length} 段…` : `Filtering segment ${index+1} / ${usable.length}…`;
          sync();
          const response = await apiFetch('/applyFilter', {
            method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({filter_config:filterConfig,raw_data:segment,record_start_sequence:record.startSeq,record_end_sequence:record.endSeq}),
          });
          if (!response.ok) throw new Error(await window.RespiraScopeShared.responseError(response));
          const result = await response.json();
          if (!result.data?.length) continue;
          const applied = result.filter_config;
          const sameBand = applied && (applied.offline_filter ?? 'bandpass') === (filterConfig.offline_filter ?? 'bandpass') && ['highpass_cutoff'].every(key=>
            Number.isFinite(applied[key]) && Math.abs(applied[key]-filterConfig[key]) <= 1e-9);
          if (!sameBand || (filterConfig.bandpass_mode === 'custom' && applied.bandpass_mode !== 'custom')) {
            throw new Error(zh()?'后端未应用所选滤波方案或参数，请检查并重启旧版后端服务后重试':'The backend did not apply the selected filter or cutoff. Check for an outdated backend, restart it and retry.');
          }
          results.push(result);
        }
        if (!results.length) throw new Error(zh()?'滤波未返回有效数据':'No filtered data returned');
      }
      if (state.lastRecord !== record) return;
      const quality = detectionOnly ? record.processingQuality : mergeQuality(results);
      if (!detectionOnly) {
        record.processingQuality = quality;
        record.filtered = results.flatMap(r=>normalizeSeries(r.data,0));
        if (record.pointTimestamps) delete record.pointTimestamps.filtered;
        record.filterStatus = 'offline';
      }
      delete record.extremaEdits;
      record.peaks = results.flatMap(r=>normalizeSeries(r.peaks ?? r.peak,0));
      record.valleys = results.flatMap(r=>normalizeSeries(r.valleys ?? r.valley,0));
      record.filterConfig = detectionOnly ? filterConfig : results[0].filter_config;
      record.metrics = results.at(-1).metrics;
      record.analysis = {...oldOptions,basis:nextBasis};
      resetDraft(record);
      busy = false;
      redraw();
    } catch (error) {
      if (state.lastRecord === record) {
        busy = false;
        failure = error.message;
        sync();
      }
    } finally {
      busy = false;
      if (state.lastRecord !== record) sync();
    }
  }
  el.basis.addEventListener('change',()=>{
    if (isBusy() || !state.lastRecord) return;
    settings().basis = el.basis.value;
    // Retain this legacy metadata field, without changing any signal parameter.
    if (state.lastRecord.filterConfig) state.lastRecord.filterConfig.processing_mode = el.basis.value;
    redraw();
  });
  el.retry.addEventListener('click',()=>refilter(el.basis.value,{useDraft:true}));
  for (const [key,field] of [['bandHigh','high'],['sensitivity','sensitivity']]) {
    el[key].addEventListener(key === 'sensitivity' ? 'change' : 'input',()=>{
      if (isBusy() || editor.isEditing() || !draft) return;
      draft.edited = true;
      if (key === 'sensitivity') draft.sensitivity = el.sensitivity.value;
      else {
        const maximum = maximumHz();
        const hz = Number((.01*Math.pow(maximum/.01,Number(el[key].value)/1000)).toPrecision(3));
        const bounded = Math.min(maximum,Math.max(hz,.01));
        draft[field] = String(Number(bounded.toPrecision(12)));
        draft.preset = false;
        syncBandSliders();
      }
      failure = null;
      sync();
    });
  }
  let dragKey = null;
  function pointerPosition(event) {
    const box = el.bandTrack.getBoundingClientRect();
    return Math.max(0,Math.min(1000,1000*(event.clientX-box.left-9)/(box.width-18)));
  }
  function moveHandle(event) {
    if (!dragKey) return;
    el[dragKey].value = String(Math.round(pointerPosition(event)));
    el[dragKey].dispatchEvent(new Event('input',{bubbles:true}));
  }
  el.bandTrack.addEventListener('pointerdown',event=>{
    if (isBusy() || editor.isEditing() || !draft || event.button !== 0) return;
    event.preventDefault();
    dragKey = 'bandHigh';
    el[dragKey].focus({preventScroll:true});
    el.bandTrack.setPointerCapture(event.pointerId);
    moveHandle(event);
  });
  el.bandTrack.addEventListener('pointermove',moveHandle);
  for (const type of ['pointerup','pointercancel','lostpointercapture']) {
    el.bandTrack.addEventListener(type,()=>{dragKey=null;});
  }
  el.discard.addEventListener('click',()=>{
    if (isBusy() || !state.lastRecord) return;
    resetDraft(state.lastRecord);
    sync();
  });
  el.reset.addEventListener('click',()=>{
    if (isBusy() || !state.lastRecord) return;
    failure = null;
    draft = {record:state.lastRecord,source:state.lastRecord.filterConfig,
      high:String(Math.min(2, maximumHz())),sensitivity:'0.3',preset:true,edited:true};
    sync();
  });
  el.totalBins.addEventListener('change',()=>{
    if (isBusy()) return;
    settings().totalBins = normalizeBinCount(Number(el.totalBins.value));
    redraw();
  });
  el.amplitudeMode.addEventListener('change',()=>{settings().amplitudeMode=el.amplitudeMode.value;redraw();});
  el.direction.addEventListener('change',()=>{settings().inhaleRising=el.direction.value==='rising';redraw();});
  for (const key of ['lower','upper']) el[key].addEventListener('change',()=>{
    if (el[key].value.trim() === '' || !Number.isFinite(Number(el[key].value))) { sync(); return; }
    updateBound(key,Number(el[key].value));
  });
  return {settings,bins,data,sync,updateBound,isBusy,hasPendingChanges,editor};
}

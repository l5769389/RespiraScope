import {findNearbyExtremum,inferExtremumType} from './extrema-search.js';
import {invalidIntervals,validSequence} from './record-quality.js';

const snapshot = record => ({peaks:record.peaks.map(p=>p.slice()),valleys:record.valleys.map(p=>p.slice())});
const sequences = marks => ({peaks:marks.peaks.map(p=>p[0]),valleys:marks.valleys.map(p=>p[0])});
// Both actions follow the horizontal position. Keep deletion narrower than snapping.
const DELETE_HIT_X_PX = 8;

// Store only original sequence identifiers; values always come from the saved curve.
export function normalizeExtremaEdits(value, filtered, quality) {
  if (value == null) return undefined;
  const points = new Map(filtered.map(p=>[p[0],p]));
  const all = new Set();
  if (value.version !== 1 || !value.automatic) throw new Error('无效的峰谷编辑记录 / Invalid extrema edits');
  const automatic = {};
  for (const key of ['peaks','valleys']) {
    const source = value.automatic[key];
    if (!Array.isArray(source)) throw new Error('无效的原始峰谷索引 / Invalid original extrema indices');
    for (const x of source) {
      if (!Number.isFinite(x) || !points.has(x) || all.has(x)) {
        throw new Error('无效的原始峰谷索引 / Invalid original extrema indices');
      }
      all.add(x);
    }
    automatic[key] = [...source].filter(x=>validSequence(x,quality?.invalidIntervals ?? [])).sort((a,b)=>a-b);
  }
  return {version:1,automatic};
}

export function createExtremaEditor({state,chartApi,getCurrentLanguage,unavailable,onChange}) {
  const el = Object.fromEntries(['edit','editor','controls','sequence','place','undo','restore','cancel','confirm','message','summary','hint','label','title','selection','mode','overview','parameterNote']
    .map(key=>[key,document.getElementById(`extrema-${key}`)]));
  let session = null, selected = null, history = [], message = '';
  const zh = () => getCurrentLanguage() === 'zh';
  const active = () => Boolean(session && session.record === state.lastRecord);
  const changed = () => {onChange();};
  function say(cn,en) {message=zh()?cn:en;sync();}
  function sync() {
    if (session && session.record !== state.lastRecord) {
      Object.assign(session.record,session.before);
      session=null;selected=null;history=[];message='';
    }
    const record=state.lastRecord;
    const editing=active();
    el.edit.disabled = !record?.filtered.length || record.filterStatus !== 'offline' || unavailable();
    el.edit.disabled ||= editing;
    for (const control of el.controls.querySelectorAll('button,input,select')) control.disabled=!editing;
    el.title.textContent=zh()?'呼吸波形':'Respiratory waveform';
    el.mode.textContent=editing?(zh()?'编辑模式':'Editing'):(zh()?'查看模式':'Viewing');
    document.getElementById('recordSection').dataset.mode=editing?'edit':'view';
    el.controls.inert=!editing;
    el.confirm.disabled=el.cancel.disabled=!editing;
    el.edit.setAttribute('aria-expanded',String(editing));
    el.parameterNote.textContent=editing
      ? (zh()?'编辑中：参数暂不可调整，退出后恢复。':'Editing: settings are locked until you exit.')
      : (zh()?'滤波参数需应用；分箱设置即时更新。':'Apply filter settings; binning changes update immediately.');
    el.overview.textContent=record?.extremaEdits
      ? (zh()?'当前使用人工校正结果，可保存记录或查看分箱数据。':'Manual corrections applied. Save the record or inspect its bins.')
      : (zh()?'当前使用自动识别结果，可进入编辑校正漏标或错标。':'Automatic extrema shown. Enter editing to correct missing or misplaced marks.');
    el.editor.classList.toggle('editing',editing);
    el.edit.textContent=zh()?'进入编辑':'Enter editing';
    const labels={undo:['撤销一步','Undo'],restore:['恢复自动标记','Restore automatic'],cancel:['取消并退出','Cancel & exit'],confirm:['应用并退出','Apply & exit'],place:['添加标记','Add marker']};
    for (const [key,label] of Object.entries(labels)) el[key].textContent=label[zh()?0:1];
    el.label.textContent=zh()?'采样序号':'Sample sequence';
    el.undo.disabled=!editing || !history.length;
    el.place.disabled=!editing;
    el.message.textContent=message;
    el.hint.textContent=editing
      ? (zh()?'按横向位置添加；点击标记正上方或下方删除。序号输入为精确添加。Ctrl / ⌘ Z 撤销，Delete / Backspace 删除当前标记。'
        :'Add by horizontal position; click above or below a marker to delete. Enter a sequence for an exact mark. Ctrl / ⌘ Z: undo; Delete / Backspace: remove the current mark.')
      : record?.extremaEdits
        ? (zh()?'已采用人工标记；重新滤波或重判峰谷会清除修改。':'Manual marks applied; recalculation or re-detection clears edits.')
        : (zh()?'查看模式仅浏览波形；滚轮缩放，底部滑块调整范围。':'Viewing does not change markers. Scroll to zoom; use the slider to adjust the range.');
    el.summary.textContent=record ? `${zh()?'波峰':'Peaks'} ${record.peaks.length} · ${zh()?'波谷':'Valleys'} ${record.valleys.length}`:'';
    el.selection.textContent=`${zh()?'已选':'Selected'} ${selected?selected.sequence:'—'}`;
    el.sequence.min=record?.filtered[0]?.[0] ?? 0;
    el.sequence.max=record?.filtered.at(-1)?.[0] ?? 0;
  }
  function begin() {
    if (unavailable() || !state.lastRecord?.filtered.length || state.lastRecord.filterStatus!=='offline') return;
    const record=state.lastRecord;
    session={record,before:snapshot(record),automatic:record.extremaEdits?.automatic ?? sequences(record)};
    history=[];selected=null;message='';el.sequence.value='';changed();
  }
  function focusChart() {chartApi.recordChart.getDom().focus({preventScroll:true});}
  function mutate(next,nextSelected=null,feedback='') {
    history.push({marks:snapshot(session.record),selected});
    if(history.length>100) history.shift();
    Object.assign(session.record,next);selected=nextSelected;
    message=feedback;changed();
  }
  function remove(mark) {
    if(!active() || unavailable() || !mark)return;
    const record=session.record;
    mutate({...snapshot(record),[mark.key]:record[mark.key].filter(p=>p[0]!==mark.sequence)},null,
      zh()?`已删除标记 · 采样 ${mark.sequence}`:`Removed marker · sample ${mark.sequence}`);
  }
  function execute(sequence,{exact=false}={}) {
    if (!active() || unavailable()) return;
    const record=session.record;
    let point=record.filtered.find(p=>p[0]===sequence && Number.isFinite(p[1]));
    if (!point) return say('请选择已有滤波采样点；不能跨越缺失数据补点。','Choose an existing filtered sample; missing data cannot be filled.');
    if (!validSequence(sequence,invalidIntervals(record))) return say('该点位于排除区间，不能添加峰谷标记。','This sample is excluded; a marker cannot be added here.');
    const options={samplingRate:record.filterConfig?.sampling_rate ?? 50,
      gap:record.filterConfig?.data_gap_reset_points ?? 25,invalidIntervals:invalidIntervals(record)};
    let key;
    if(exact) {
      const existing=['peaks','valleys'].find(k=>record[k].some(p=>p[0]===sequence));
      if(existing){selected={key:existing,sequence};message=zh()?'该点已有标记，已选中。':'Existing marker selected.';changed();focusChart();return;}
      key=inferExtremumType(record.filtered,sequence,options);
      if(!key)return say('该位置附近无法区分峰谷，请选择转折附近的采样序号。','Cannot determine peak or valley here; choose a sequence near a turn.');
    } else {
      const candidate=findNearbyExtremum(record.filtered,sequence,options);
      if(!candidate)return say('附近未找到峰谷；可输入转折位置的采样序号精确添加。','No extremum nearby; enter a sample sequence near the turn for an exact mark.');
      point=candidate.point;sequence=point[0];key=candidate.key;
    }
    const existing=['peaks','valleys'].find(k=>record[k].some(p=>p[0]===sequence));
    if(existing)return say('附近峰谷已有标记；点击标记或其正上方、正下方可删除。','The nearby extremum is already marked; click on, directly above or below its marker to delete it.');
    const next=snapshot(record);
    next[key].push(point.slice(0,2));next[key].sort((a,b)=>a[0]-b[0]);
    el.sequence.value=String(sequence);
    mutate(next,{key,sequence},zh()?`已添加${key==='peaks'?'波峰':'波谷'} · 采样 ${sequence}`:`Added ${key==='peaks'?'peak':'valley'} · sample ${sequence}`);
    focusChart();
  }
  function chartClick(pixel) {
    if (!active() || unavailable()) return;
    const chart=chartApi.recordChart;
    if (!chart.containPixel({gridIndex:0},pixel)) return;
    focusChart();
    const candidates=['peaks','valleys'].flatMap(key=>session.record[key].map(point=>{
      const xy=chart.convertToPixel({gridIndex:0},point);
      return {key,sequence:point[0],distance:Math.abs(xy[0]-pixel[0]),verticalDistance:Math.abs(xy[1]-pixel[1])};
    })).sort((a,b)=>a.distance-b.distance || a.verticalDistance-b.verticalDistance);
    if(candidates[0]?.distance<=DELETE_HIT_X_PX){remove(candidates[0]);return;}
    const [x]=chart.convertFromPixel({gridIndex:0},pixel);
    const points=session.record.filtered;
    let lo=0,hi=points.length;
    while(lo<hi){const mid=(lo+hi)>>1;if(points[mid][0]<x)lo=mid+1;else hi=mid;}
    if(lo>0 && lo<points.length && x>points[lo-1][0] && x<points[lo][0] && points[lo][0]-points[lo-1][0]>(session.record.filterConfig?.data_gap_reset_points ?? 25)) {
      return say('此处为数据缺口，不能添加标记。','This is a data gap; a marker cannot be added.');
    }
    const nearest=[points[lo-1],points[lo]].filter(Boolean).sort((a,b)=>Math.abs(a[0]-x)-Math.abs(b[0]-x))[0];
    if(nearest)execute(nearest[0]);
  }
  function undo() {
    if(!active() || unavailable() || !history.length)return;
    const previous=history.pop();Object.assign(session.record,previous.marks);selected=previous.selected;message='';changed();
  }
  document.addEventListener('keydown',event=>{
    if(!active() || unavailable() || event.repeat || event.isComposing || document.querySelector('dialog[open]'))return;
    const target=event.target;
    if(target.isContentEditable || target.closest('input,textarea,select') || !target.closest('#extrema-editor,#recordChart'))return;
    if((event.ctrlKey || event.metaKey) && !event.shiftKey && !event.altKey && event.key.toLowerCase()==='z') {
      event.preventDefault();undo();
    } else if(!event.ctrlKey && !event.metaKey && !event.altKey && ['Delete','Backspace'].includes(event.key)) {
      event.preventDefault();remove(selected);
    }
  });
  el.edit.addEventListener('click',begin);
  el.place.addEventListener('click',()=>{
    if(el.sequence.value.trim()) execute(Number(el.sequence.value),{exact:true});
  });
  el.sequence.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();el.place.click();}});
  el.undo.addEventListener('click',undo);
  el.restore.addEventListener('click',()=>{
    if(!active())return;
    const points=new Map(session.record.filtered.map(p=>[p[0],p]));
    mutate(Object.fromEntries(['peaks','valleys'].map(key=>[key,session.automatic[key].map(x=>points.get(x)).filter(Boolean).map(p=>p.slice(0,2))])));
  });
  el.cancel.addEventListener('click',()=>{
    if(!active())return;
    Object.assign(session.record,session.before);session=null;selected=null;message=zh()?'已取消本次修改，返回查看模式。':'Changes cancelled; returned to viewing.';changed();
  });
  el.confirm.addEventListener('click',()=>{
    if(!active())return;
    const {record,automatic}=session;
    if(JSON.stringify(sequences(record))===JSON.stringify(automatic)) delete record.extremaEdits;
    else record.extremaEdits={version:1,automatic};
    session=null;selected=null;message=zh()?'修改已应用；可点击“保存记录”导出。':'Changes applied; save the record to export them.';changed();
  });
  return {sync,isEditing:active,chartClick,selected:()=>active()?selected:null};
}

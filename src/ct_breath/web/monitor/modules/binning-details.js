export function createBinningDetails({getData,getTimeline,getCurrentLanguage}) {
  const byId=id=>document.getElementById(id);
  const dialog=byId('binningDataDialog'),button=byId('binningDataBtn'),filter=byId('binningStatusFilter');
  let snapshot=null,timeline=null,page=0,jsonView=false;
  const zh=()=>getCurrentLanguage()==='zh';
  const label=status=>({valid:zh()?'有效':'Valid',excluded:zh()?'排除':'Excluded',unassigned:zh()?'无法分箱':'Unassigned'})[status];
  const text=(id,cn,en)=>{byId(id).textContent=zh()?cn:en;};
  function renderRows() {
    if(!snapshot)return;
    const rows=timeline.intervals.filter(r=>filter.value==='all'||r.status===filter.value);
    const pages=Math.max(1,Math.ceil(rows.length/100));page=Math.min(page,pages-1);
    const tbody=byId('binningDataRows');tbody.replaceChildren();
    for(const row of rows.slice(page*100,(page+1)*100)){
      const tr=document.createElement('tr');
      const cells=[`${((row.start-timeline.range[0])/timeline.samplingRateHz).toFixed(3)} – ${((row.end-timeline.range[0])/timeline.samplingRateHz).toFixed(3)}`,
        `${Number(row.start.toFixed(3))} – ${Number(row.end.toFixed(3))}`,label(row.status),
        row.direction ? `${row.direction==='inhale'?(zh()?'吸气':'Inhale'):(zh()?'呼气':'Exhale')} ${row.bin}` : '—'];
      cells.forEach((value,i)=>{const td=document.createElement('td');if(i===2){const badge=document.createElement('span');badge.className=`binning-badge ${row.status}`;badge.textContent=value;td.append(badge);}else td.textContent=value;tr.append(td);});
      tbody.append(tr);
    }
    if(!rows.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=4;td.className='binning-empty';td.textContent=zh()?'此状态下没有区间':'No intervals with this status';tr.append(td);tbody.append(tr);}
    text('binningDataPage',`${rows.length} 个区间 · 第 ${page+1} / ${pages} 页`,`${rows.length} intervals · Page ${page+1} / ${pages}`);
    byId('binningDataPrev').disabled=page===0;byId('binningDataNext').disabled=page===pages-1;
  }
  function setView(json) {
    jsonView=json;
    byId('binningTablePanel').hidden=json;byId('binningJsonPanel').hidden=!json;
    byId('binningStatusLabel').hidden=json;
    byId('binningTableTab').setAttribute('aria-pressed',String(!json));byId('binningJsonTab').setAttribute('aria-pressed',String(json));
    if(json && snapshot)byId('binningDataJson').textContent=[
      '{',`  "version": ${snapshot.version},`,`  "inhaleRising": ${snapshot.inhaleRising},`,'  "bins": {',
      `    "inhale": ${JSON.stringify(snapshot.bins.inhale)},`,
      `    "exhale": ${JSON.stringify(snapshot.bins.exhale)}`,'  },',
      `  "excluded": ${JSON.stringify(snapshot.excluded)},`,
      `  "unassigned": ${JSON.stringify(snapshot.unassigned)}`,'}',
    ].join('\n');
  }
  function render() {
    snapshot=getData();timeline=getTimeline();if(!snapshot||!timeline)return;
    text('binningDataTitle','分箱数据','Binning data');text('binningDataClose','关闭','Close');
    text('binningDataIntro','记录范围内的完整分箱时间轴，分为有效、排除、无法分箱。仅有效区间有方向和箱号。','Complete binning timeline: valid, excluded and unassigned. Only valid intervals have a direction and bin number.');
    text('binningTableTab','区间明细','Intervals');text('binningJsonTab','存储 JSON','Stored JSON');
    text('binningDataDownload','导出分箱 JSON','Export binning JSON');
    text('binningDataPrev','上一页','Previous');text('binningDataNext','下一页','Next');
    byId('binningStatusLabel').querySelector('span').textContent=zh()?'状态':'Status';
    for(const option of filter.options)option.textContent=option.value==='all'?(zh()?'全部':'All'):label(option.value);
    const head=byId('binningDataHead');head.replaceChildren();const tr=document.createElement('tr');
    for(const value of zh()?['相对时间 / 秒','采样序号','状态','方向 / 箱号']:['Relative time / s','Sample sequence','Status','Direction / bin']){const th=document.createElement('th');th.scope='col';th.textContent=value;tr.append(th);}head.append(tr);
    const summary=byId('binningDataSummary');summary.replaceChildren();
    for(const status of ['valid','excluded','unassigned']){
      const rows=timeline.intervals.filter(r=>r.status===status),seconds=rows.reduce((sum,r)=>sum+r.end-r.start,0)/timeline.samplingRateHz;
      const card=document.createElement('article');card.className=status;
      const name=document.createElement('span'),value=document.createElement('strong'),count=document.createElement('small');
      name.textContent=label(status);value.textContent=`${seconds.toFixed(2)} s`;count.textContent=zh()?`${rows.length} 个区间`:`${rows.length} intervals`;card.append(name,value,count);summary.append(card);
    }
    text('binningJsonHelp',`吸气方向：信号${snapshot.inhaleRising?'上升':'下降'}（inhaleRising = ${snapshot.inhaleRising}）。bins 仅包含有效数据；inhale 为吸气，exhale 为呼气，各数组依次为第 1 至 ${snapshot.bins.inhale.length} 箱。excluded 为排除，unassigned 为无法分箱。所有 [起点, 终点) 均为完整 filtered 数组下标。`,
      `Inhale direction: signal ${snapshot.inhaleRising?'rising':'falling'} (inhaleRising = ${snapshot.inhaleRising}). bins contains valid data only; inhale / exhale list bins 1–${snapshot.bins.inhale.length}. excluded and unassigned list the other intervals. All [start, end) ranges index the complete filtered array.`);
    text('binningDataFooter','表格展示连续区间，采样序号可含小数；JSON 将边界映射到首个不早于边界的采样下标，只保存实际分配的点。相对时间按采样率换算，不是 CT 同步时间。末点为右边界，缓冲不参与分箱，数组下标不重新编号。','The table shows continuous intervals with fractional sequence coordinates. JSON maps each boundary to the first sample at or after it and stores assigned samples only. Relative time is derived from the sample rate, not CT synchronization time. The final sample is the right boundary; padding is not binned and indexes are never renumbered.');
    renderRows();setView(jsonView);
  }
  button.addEventListener('click',()=>{page=0;filter.value='all';jsonView=false;render();dialog.showModal();});
  byId('binningDataClose').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('click',event=>{if(event.target===dialog){const b=dialog.getBoundingClientRect();if(event.clientX<b.left||event.clientX>b.right||event.clientY<b.top||event.clientY>b.bottom)dialog.close();}});
  filter.addEventListener('change',()=>{page=0;renderRows();});
  byId('binningTableTab').addEventListener('click',()=>setView(false));byId('binningJsonTab').addEventListener('click',()=>setView(true));
  byId('binningDataPrev').addEventListener('click',()=>{page--;renderRows();});byId('binningDataNext').addEventListener('click',()=>{page++;renderRows();});
  byId('binningDataDownload').addEventListener('click',()=>{
    if(!snapshot)return;
    const url=URL.createObjectURL(new Blob([JSON.stringify(snapshot)],{type:'application/json'}));
    const link=document.createElement('a');link.href=url;link.download='respirascope-binning.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  return {sync(disabled){button.disabled=disabled;text('binningDataBtn','分箱数据','Binning data');if(dialog.open){if(disabled)dialog.close();else render();}}};
}

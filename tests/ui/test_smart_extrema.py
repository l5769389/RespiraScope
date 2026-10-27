import json
import math

from playwright.sync_api import expect


def smart_record(page,ui_server,tmp_path):
    points=[[i,100+40*math.cos(2*math.pi*(i-100)/200)] for i in range(401)]
    record={'version':6,'raw':points,'filtered':points,'peaks':[],'valleys':[],
            'startSeq':0,'endSeq':400,'filterStatus':'offline',
            'analysis':{'basis':'time','totalBins':10,'inhaleRising':True},
            'filterConfig':{'offline_filter':'baseline_lowpass','highpass_cutoff':2,'sampling_rate':50},
            'processingQuality':{'version':2,'baselines':[],'invalidIntervals':[{'start':290,'end':310,'reason':'motion'}]}}
    file=tmp_path/'smart.json';file.write_text(json.dumps(record))
    page.goto(ui_server['ui']+'/monitor/');page.locator('#loadRecordInput').set_input_files(file)
    page.locator('#recordSection').wait_for(state='visible')
    return record


def point_click(page,sequence,value):
    chart=page.locator('#recordChart');chart.scroll_into_view_if_needed()
    xy=chart.evaluate('(el,p)=>echarts.getInstanceByDom(el).convertToPixel({gridIndex:0},p)',[sequence,value])
    chart.click(position={'x':xy[0],'y':xy[1]})


def marks(page):
    return page.locator('#recordChart').evaluate('''el=>{
      const c=echarts.getInstanceByDom(el),o=c.getOption();
      return {peaks:o.series.find(s=>s.id==='peaks').data,valleys:o.series.find(s=>s.id==='valleys').data,zoom:o.dataZoom};
    }''')


def layout(page):
    return page.evaluate('''()=>['recordChart','extrema-editor','analysis-status'].map(id=>{
      const r=document.getElementById(id).getBoundingClientRect();return [r.x,r.y+scrollY,r.width,r.height];
    })''')


def test_auto_add_snaps_to_turn_and_stable_layout(page,ui_server,tmp_path):
    record=smart_record(page,ui_server,tmp_path)
    before=layout(page)
    page.locator('#extrema-edit').click()
    assert page.locator('#extrema-tool').count()==0
    assert layout(page)==before
    point_click(page,91,record['filtered'][91][1])
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 1')
    expect(page.locator('#extrema-sequence')).to_have_value('100')
    point_click(page,213,record['filtered'][213][1])
    expect(page.locator('#extrema-summary')).to_contain_text('波谷 1')
    expect(page.locator('#extrema-sequence')).to_have_value('200')
    stable=layout(page)
    page.locator('#extrema-sequence').fill('9999')
    page.locator('#extrema-place').click()
    expect(page.locator('#extrema-message')).to_contain_text('已有滤波采样点')
    assert layout(page)==stable
    point_click(page,300,140)
    expect(page.locator('#extrema-message')).to_contain_text('排除')
    assert layout(page)==stable
    page.locator('#extrema-undo').click()
    assert layout(page)==stable
    page.locator('#extrema-confirm').click()
    assert layout(page)==stable
    page.locator('#recordSection').screenshot(path=str(tmp_path/'smart-desktop.png'))
    page.set_viewport_size({'width':390,'height':844})
    stable=layout(page);page.locator('#extrema-edit').click()
    assert layout(page)==stable
    assert page.locator('#extrema-editor').evaluate('el=>el.scrollWidth<=el.clientWidth')
    page.locator('#extrema-editor').screenshot(path=str(tmp_path/'smart-mobile.png'))


def test_turn_search_rejects_gap_noise_and_handles_plateau(page,ui_server,tmp_path):
    smart_record(page,ui_server,tmp_path)
    result=page.evaluate('''async()=>{
      const {findNearbyExtremum:f}=await import('./modules/extrema-search.js');
      const opts={samplingRate:50,gap:25,invalidIntervals:[]};
      const triangle=Array.from({length:101},(_,i)=>[i,i<45?i:i<=55?45:100-i]);
      const mono=Array.from({length:201},(_,i)=>[i,i]);
      const ripple=mono.map(([x,y])=>[x,y+(x%2)*1.2]);
      const gap=triangle.filter(p=>p[0]<40||p[0]>60);
      return {plateau:f(triangle,48,opts),mono:f(mono,50,opts),ripple:f(ripple,50,opts),gap:f(gap,50,opts),
        mask:f(triangle,35,{...opts,invalidIntervals:[{start:40,end:60}]}),edge:f(mono,0,opts)};
    }''')
    assert result['plateau']['key']=='peaks' and result['plateau']['point'][0]==50
    assert all(result[k] is None for k in ['mono','ripple','gap','mask','edge']), result


def test_auto_edit_preserves_zoom_when_toggling_marks(page,ui_server,tmp_path):
    record=smart_record(page,ui_server,tmp_path)
    chart=page.locator('#recordChart')
    chart.evaluate("el=>echarts.getInstanceByDom(el).dispatchAction({type:'dataZoom',start:20,end:60})")
    before=marks(page)['zoom']
    page.locator('#extrema-edit').click()
    point_click(page,105,record['filtered'][105][1])
    expect(page.locator('#extrema-sequence')).to_have_value('100')
    point_click(page,103,record['filtered'][103][1])
    expect(page.locator('#extrema-message')).to_contain_text('已有标记')
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 1')
    point_click(page,100,140)
    expect(page.locator('#extrema-message')).to_contain_text('已删除')
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 0')
    after=marks(page)['zoom']
    assert [(z['start'],z['end']) for z in before]==[(z['start'],z['end']) for z in after]
    page.locator('#extrema-cancel').click()
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 0')

import pytest

from playwright.sync_api import expect
from test_smart_extrema import smart_record,point_click,layout


def exact(page,sequence):
    page.locator('#extrema-sequence').fill(str(sequence))
    page.locator('#extrema-place').click()


def test_click_toggle_exact_sequence_and_keyboard(page,ui_server,tmp_path):
    record=smart_record(page,ui_server,tmp_path)
    page.locator('#extrema-edit').click()
    assert page.locator('#extrema-tool').count()==0
    stable=layout(page)
    point_click(page,91,record['filtered'][91][1])
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 1')
    # Wide snapping is for adding only; deleting uses a narrow horizontal hit.
    point_click(page,91,record['filtered'][91][1])
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 1')
    expect(page.locator('#extrema-message')).to_contain_text('已有标记')
    point_click(page,100,140)
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 0')
    page.keyboard.press('Control+z')
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 1')
    page.keyboard.press('Meta+z')
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 0')
    exact(page,97)
    expect(page.locator('#extrema-selection')).to_contain_text('97')
    expect(page.locator('#extrema-sequence')).to_have_value('97')
    page.keyboard.press('Delete')
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 0')
    page.keyboard.press('Control+z')
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 1')
    # Native editing keys must not mutate chart markers inside the number field.
    page.locator('#extrema-sequence').fill('200')
    page.locator('#extrema-sequence').press('Backspace')
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 1')
    exact(page,201)
    expect(page.locator('#extrema-summary')).to_contain_text('波谷 1')
    page.keyboard.press('Backspace')
    expect(page.locator('#extrema-summary')).to_contain_text('波谷 0')
    assert layout(page)==stable
    page.locator('#recordSection').screenshot(path=str(tmp_path/'simple-editor.png'))


def test_search_accepts_sparse_samples_and_turn_close_to_mask(page,ui_server,tmp_path):
    smart_record(page,ui_server,tmp_path)
    result=page.evaluate('''async()=>{
      const {findNearbyExtremum:f}=await import('./modules/extrema-search.js');
      const points=Array.from({length:201},(_,i)=>[i,100+40*Math.cos((i-100)*Math.PI/100)]);
      const options={samplingRate:50,gap:25,invalidIntervals:[]};
      return {sparse:f(points.filter(p=>p[0]%2===0),96,options),
        edge:f(points,98,{...options,invalidIntervals:[{start:104,end:150}]}),
        low:f(points.map(([x,y])=>[x,100+(y-100)*1e-6]),98,options)};
    }''')
    assert all(r and r['key']=='peaks' and r['point'][0]==100 for r in result.values()),result


def test_same_position_below_curve_adds_then_deletes(page,ui_server,tmp_path):
    smart_record(page,ui_server,tmp_path)
    page.locator('#extrema-edit').click()
    point_click(page,100,95)
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 1')
    point_click(page,100,95)
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 0')
    page.keyboard.press('Control+z')
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 1')


@pytest.mark.parametrize('sequence,value,label',[(100,140,'波峰'),(200,60,'波谷')])
@pytest.mark.parametrize('zoom',[(0,100),(20,60)])
def test_delete_has_small_screen_hit_area(page,ui_server,tmp_path,sequence,value,label,zoom):
    smart_record(page,ui_server,tmp_path)
    chart=page.locator('#recordChart')
    chart.evaluate('(el,z)=>echarts.getInstanceByDom(el).dispatchAction({type:"dataZoom",start:z[0],end:z[1]})',list(zoom))
    page.locator('#extrema-edit').click()
    exact(page,sequence)
    chart.scroll_into_view_if_needed()
    xy=chart.evaluate('(el,p)=>echarts.getInstanceByDom(el).convertToPixel({gridIndex:0},p)',[sequence,value])
    # The narrow x hit is independent of y and zoom; wide search never deletes.
    dy=100 if label=='波峰' else -100
    for dx,offset_y in [(11,0),(11,dy)]:
        chart.click(position={'x':xy[0]+dx,'y':xy[1]+offset_y})
        expect(page.locator('#extrema-summary')).to_contain_text(f'{label} 1')
        expect(page.locator('#extrema-message')).to_contain_text('已有标记')
    chart.click(position={'x':xy[0]+4,'y':xy[1]+dy})
    expect(page.locator('#extrema-summary')).to_contain_text(f'{label} 0')
    page.keyboard.press('Control+z')
    expect(page.locator('#extrema-summary')).to_contain_text(f'{label} 1')
    page.keyboard.press('Control+z')
    expect(page.locator('#extrema-summary')).to_contain_text(f'{label} 0')

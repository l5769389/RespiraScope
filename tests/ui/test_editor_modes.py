from playwright.sync_api import expect
from test_smart_extrema import smart_record,point_click,layout
from test_simple_extrema import exact


def test_view_edit_apply_cancel_modes_and_stable_layout(page,ui_server,tmp_path):
    smart_record(page,ui_server,tmp_path)
    expect(page.locator('#extrema-mode')).to_have_text('查看模式')
    expect(page.locator('#extrema-edit')).to_have_text('进入编辑')
    expect(page.locator('#extrema-controls')).not_to_be_visible()
    expect(page.locator('#extrema-confirm')).not_to_be_visible()
    point_click(page,100,140)
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 0')
    before=layout(page)
    page.locator('#recordSection').screenshot(path=str(tmp_path/'analysis-view.png'))
    page.locator('#extrema-edit').click()
    expect(page.locator('#extrema-mode')).to_have_text('编辑模式')
    expect(page.locator('#extrema-edit')).not_to_be_visible()
    expect(page.locator('#extrema-confirm')).to_have_text('应用并退出')
    expect(page.locator('#extrema-cancel')).to_have_text('取消并退出')
    expect(page.locator('#extrema-controls')).to_be_visible()
    expect(page.locator('#analysis-basis')).to_be_disabled()
    assert layout(page)==before
    exact(page,97)
    page.locator('#recordSection').screenshot(path=str(tmp_path/'analysis-edit.png'))
    page.locator('#extrema-cancel').click()
    expect(page.locator('#extrema-mode')).to_have_text('查看模式')
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 0')
    assert layout(page)==before
    page.locator('#extrema-edit').click();exact(page,100)
    page.locator('#extrema-confirm').click()
    expect(page.locator('#extrema-summary')).to_contain_text('波峰 1')
    expect(page.locator('#extrema-mode')).to_have_text('查看模式')
    expect(page.locator('#saveRecordBtn')).to_be_enabled()
    assert layout(page)==before
    page.set_viewport_size({'width':390,'height':844})
    before=layout(page)
    page.locator('#extrema-edit').click()
    assert layout(page)==before
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.locator('.record-wave-panel').screenshot(path=str(tmp_path/'analysis-edit-mobile.png'))
    page.locator('#extrema-cancel').click()
    assert layout(page)==before

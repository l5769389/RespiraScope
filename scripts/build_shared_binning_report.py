"""Build the comparison DOCX from reviewed measurements and figures.
Run with the document workspace's bundled Python (python-docx).
"""
from pathlib import Path
import json
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'docs/measurements/shared_binning'
OUT=ROOT/'docs/统一低通后时间与幅值分箱对比报告.docx'
rows=json.loads((DATA/'metrics.json').read_text())['rows']
# Retain the previous waveform report's landscape page system, adding the requested result column.
d=Document(ROOT/'docs/带缓冲的一分钟波形对比.docx')
for e in list(d._element.body):
    if e.tag!=qn('w:sectPr'): d._element.body.remove(e)
# Drop old illustration relationships when replacing the reference body.
for rid, rel in list(d.part.rels.items()):
    if rel.reltype.endswith('/image'): d.part.drop_rel(rid)
sec=d.sections[0]
sec.page_width=Inches(11.69);sec.page_height=Inches(8.27)
sec.top_margin=sec.bottom_margin=Inches(.4);sec.left_margin=sec.right_margin=Inches(.4)
sec.header_distance=sec.footer_distance=Inches(.16)
for name,size in [('Normal',10.5),('Title',22),('Heading 1',14),('Caption',9)]:
    st=d.styles[name];st.font.name='Arial';st.font.size=Pt(size);st.font.color.rgb=RGBColor.from_string('000000' if name in ('Title','Heading 1') else '182230')
    st.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'Hiragino Sans GB')
    st.paragraph_format.space_before=Pt(0);st.paragraph_format.space_after=Pt(5)
    st.paragraph_format.line_spacing=Pt(30 if name=='Title' else 19 if name=='Heading 1' else 12 if name=='Caption' else 15)
    st.font.bold=name=='Heading 1'
    snap=OxmlElement('w:snapToGrid');snap.set(qn('w:val'),'0');st.element.get_or_add_pPr().append(snap)
    st.paragraph_format.keep_with_next=False
    for border in list(st.element.iter(qn('w:pBdr'))):border.getparent().remove(border)
footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
footer.text='RespiraScope  ·  模拟测算  ·  '
fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');footer._p.append(fld)
for r in footer.runs:r.font.size=Pt(8)

def para(t,style=None):return d.add_paragraph(t,style)

def table(headers,widths):
    t=d.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
    for col,w in zip(t.columns,widths):col.width=Inches(w)
    for c,tx in zip(t.rows[0].cells,headers):c.text=tx
    repeat=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(repeat)
    return t

def style_table(t,widths,compact=False):
    for i,row in enumerate(t.rows):
        no=OxmlElement('w:cantSplit');row._tr.get_or_add_trPr().append(no)
        for c,w in zip(row.cells,widths):
            c.width=Inches(w);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            pr=c._tc.get_or_add_tcPr();mar=OxmlElement('w:tcMar')
            for side in ['top','left','bottom','right']:
                e=OxmlElement('w:'+side);e.set(qn('w:w'),'45' if compact and side in ['top','bottom'] else '75');e.set(qn('w:type'),'dxa');mar.append(e)
            pr.append(mar);borders=OxmlElement('w:tcBorders')
            for side in ['top','left','bottom','right']:
                e=OxmlElement('w:'+side);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
            pr.append(borders)
            if i==0:
                sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'E8EEF6');pr.append(sh)
            for p in c.paragraphs:
                p.paragraph_format.space_after=Pt(2 if compact else 4);p.paragraph_format.keep_with_next=False
                p.paragraph_format.line_spacing=1 if p._p.xpath('.//w:drawing | .//m:oMath') else Pt(12.5)
                for r in p.runs:
                    r.font.size=Pt(9.5)
                    if i==0:r.bold=True

def fmt(value):
    return '—' if value is None else f'{value:.2f}%'


def lag_text(raw):
    value=raw['lag_ms_median']
    text='—' if value is None else f'{value:+.0f}' if value else '0'
    return text if raw['lag_runs']==20 else f"{text}\n（{raw['lag_runs']}／20 次）"


def add_metric(cell,label,value):
    p=cell.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(f'{label} {fmt(value)}')

by_id={r['id']:r for r in rows}
normal=by_id['normal']['reference_comparison']['modes']
weak=by_id['weak_noisy']['reference_comparison']['modes']
cough=by_id['cough_artifact']['reference_comparison']
para('时间分箱与固定幅值分箱结果核对','Title')
para('本报告比较两种分箱在噪声和异常信号影响下，与各自无噪声参考划分的一致程度。共 16 种模拟呼吸状态，每种 20 次，每周期 10 箱。')
para('测算结果','Heading 1')
para(f"正常呼吸时，时间分箱与参考不一致的时间点占 {normal['time']['mismatch_percent']:.2f}%，固定幅值分箱为 {normal['fixed']['mismatch_percent']:.2f}%；低幅强噪声下分别升至 {weak['time']['mismatch_percent']:.2f}% 和 {weak['fixed']['mismatch_percent']:.2f}%。噪声相对呼吸幅值增大时，两种方式都更难保持原有划分。")
para(f"密集咳嗽与冲击伪影仅有 {cough['scored_percent']:.2f}% 的记录可共同核对，结果只代表保留片段。时间与幅值分箱采用不同目标区间，本报告不据此评选总体最优方案。")
para('指标与比较对象','Heading 1')
widths=[2.0,5.65,3.2]
t=table(['指标','如何理解','比较对象与范围'],widths)
for values in [
 ('参考分箱不一致率','同一时刻，实际的吸呼方向或箱号与自身参考划分不同的点数比例。相邻箱的轻微跨界也计入。','两种方式在相同时间点核对；各自使用对应规则的参考箱。'),
 ('共同核对范围','既被两种方式分箱、又有参考划分的时间点，占整段记录的比例。','这是结果适用范围，不是准确率；未分箱的点不算正确。'),
 ('幅值误差 RMSE','处理曲线与无噪声参考曲线逐点差值的均方根，用一个数概括误差大小。','除以预设呼吸峰峰值，以 % 表示；两种方式共用同一曲线。'),
 ('幅值误差 P95','95% 的逐点绝对误差不超过此数值；剩余 5% 可能更大。','相对无噪声参考，使用与 RMSE 相同的单位和有效区间。'),
 ('相对原始幅值差','同一时刻处理值与原始值的平均绝对差，占原始幅值跨度的百分比。','原始数据含噪声和伪影；差距含去噪效果，不能直接当成误差。'),
 ('整体时间偏移','原始与处理曲线整体对齐的时间差，单位 ms；正值为处理后滞后，负值为提前。','汇总可估计次数的中位数；不代表每个峰谷的时间偏差。'),
]:
    for c,v in zip(t.add_row().cells,values):c.text=v
style_table(t,widths)
para('参考如何建立','Heading 1')
para('从未加入噪声和伪影的模拟曲线独立定位峰谷。时间参考将每个峰谷之间的半周期等分为 5 箱；幅值参考按同一组上下限，将参考幅值分为吸气、呼气各 5 箱。实际幅值分箱若收录了参考幅值越界的点，也计为不一致。','Caption')
para('不一致率按 20 次模拟合并点数计算，不把没有可核对点的模拟记为零误差。曲线误差只统计质量判定保留的有效区间；幅值上下限沿用本次记录的默认设置。','Caption')
para('模拟“屏气与呼吸暂停”和“周期性减弱”仍保留最低 8% 的呼吸振荡；这些状态的分箱核对不等于暂停识别验证。所有结果仅说明软件模拟表现，不直接代表器官位置或 CT 重建质量。','Caption')

d.add_page_break()
para('各呼吸状态的参考核对总览','Heading 1')
para('左列核对两种分箱与各自参考划分的一致性；中列给出相同核对范围；右列为共用处理曲线的幅值误差。各列使用独立刻度。','Caption')
p=para('');p.paragraph_format.line_spacing=1
p.add_run().add_picture(str(DATA/'figures/scenario_overview.png'),width=Inches(10.8))
para(f"密集咳嗽与冲击伪影的核对点仅占 {cough['scored_percent']:.2f}%，来自 {cough['scored_runs']}／20 次模拟；其余状态均有 20 次可核对数据。曲线误差另按质量有效区间计算，范围见下一页。",'Caption')
para('分箱不一致率的参考定义不同，数值表示各自规则对当前信号扰动的敏感程度，不能直接推导 CT 重建效果的优劣。','Caption')

d.add_page_break()
para('共用处理曲线的幅值与时间差异','Heading 1')
para('时间分箱与固定幅值分箱的处理曲线相同，下表只列一次。前两项误差以无噪声参考为标准；后两项差异以含噪声的原始数据为标准。','Caption')
widths=[2.25,1.6,1.6,1.8,1.8,1.8]
t=table(['呼吸状态','幅值误差\nRMSE / %','幅值误差\nP95 / %','相对原始\n幅值差 / %','相对原始\n整体偏移 / ms','质量有效\n区间 / %'],widths)
for row in rows:
    values=[row['name'],f"{row['filter_nrmse']:.2f}",f"{row['filter_error_p95']:.2f}",
            f"{row['raw_comparison']['mae_percent']:.2f}",lag_text(row['raw_comparison']),f"{row['valid_percent']:.2f}"]
    for i,(c,v) in enumerate(zip(t.add_row().cells,values)):
        c.text=v
        if i:
            c.paragraphs[0].alignment=WD_ALIGN_PARAGRAPH.CENTER
style_table(t,widths,compact=True)
para('RMSE 和 P95 按全部有效点合并计算；相对原始幅值差取 20 次模拟平均值。质量有效区间可能包含未能组成完整峰谷段的点，因此比共同分箱核对范围更大。','Caption')
para('整体偏移以 20 ms 为步长估计；0 ms 只表示未检出整体移位，不表示局部没有偏移。“—”表示连续有效片段不足或无法可靠对齐；括号注明可估计次数。原始幅值跨度取第 95 与第 5 百分位之差。','Caption')
para('幅值误差是在各状态保留的有效区间内测得。异常状态大量数据被排除后，即使误差数值不大，也不能据此认为整段记录恢复良好。','Caption')

widths=[.85,3.45,3.45,1.5,1.6]
for offset in range(0,len(rows),2):
    d.add_page_break()
    para(f'波形与分箱核对 {offset+1} 至 {min(offset+2,len(rows))}','Heading 1')
    para('图示为一次模拟，数值汇总 20 次。原始信号为灰线，处理信号为蓝线，无噪声参考为绿线；橙虚线表示不参与分箱的参考显示。纵轴为模拟传感器单位。','Caption')
    para('底部蓝色带为吸气、黄色带为呼气，深浅区分箱号；空白为未分箱。时间分箱用竖虚线标边界，固定幅值分箱用横线标幅值范围及边界。','Caption')
    t=table(['呼吸状态','时间分箱','固定幅值分箱','共同核对范围','已分箱数据'],widths)
    for row in rows[offset:offset+2]:
        cells=t.add_row().cells;cells[0].text=row['name']
        result=row['reference_comparison']
        for c,mode in zip(cells[1:3],['time','fixed']):
            p=c.paragraphs[0];p.paragraph_format.line_spacing=1
            p.add_run().add_picture(str(DATA/'figures'/f"{row['id']}_{mode}.png"),width=Inches(3.29))
            add_metric(c,'参考不一致率',result['modes'][mode]['mismatch_percent'])
        cells[3].text=f"占整段记录\n{result['scored_percent']:.2f}%"
        cells[3].add_paragraph(f"可核对次数\n{result['scored_runs']}／20")
        cells[4].text=f"时间分箱\n{row['modes']['time']['coverage']:.2f}%"
        cells[4].add_paragraph(f"固定幅值分箱\n{row['modes']['fixed']['coverage']:.2f}%")
    style_table(t,widths)
    para('已分箱数据仅说明数据去向，不作为准确性排名。幅值范围之外、质量判定排除和不完整峰谷段等均可能导致未分箱。','Caption')

d.core_properties.title='时间分箱与固定幅值分箱结果核对'
d.core_properties.subject='基于无噪声模拟参考的分箱核对'
d.core_properties.author='RespiraScope'
d.save(OUT)
print(OUT)

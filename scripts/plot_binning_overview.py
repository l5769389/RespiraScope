"""Export the report's aligned scenario overview from existing measured results."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs/measurements/shared_binning'
FONT = FontProperties(fname='/System/Library/Fonts/Hiragino Sans GB.ttc')
COLORS = {'time': '#3266B6', 'fixed': '#118478', 'shared': '#727D8D'}


def main():
    rows = json.loads((DATA / 'metrics.json').read_text())['rows']
    plt.rcParams.update({'font.family': FONT.get_name(), 'font.size': 11,
                         'axes.unicode_minus': False})
    fig, axes = plt.subplots(1, 3, figsize=(13, 7.1), sharey=True,
                             gridspec_kw={'width_ratios': [1.3, 1, 1]})
    fig.subplots_adjust(left=.175, right=.985, top=.86, bottom=.065, wspace=.22)
    y = np.arange(len(rows))
    for ax in axes:
        for i in range(len(rows)):
            if i % 2 == 0:
                ax.axhspan(i-.5, i+.5, color='#F2F5F8', zorder=0)
        ax.set_ylim(len(rows)-.5, -.5)
        ax.grid(axis='x', color='#E0E5EB', lw=.6, zorder=0)
        ax.set_axisbelow(True)
        ax.tick_params(axis='both', length=0, labelsize=10)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.axvline(0, color='#A8B1BE', lw=.7)
    axes[0].set_yticks(y, [r['name'].replace('密集咳嗽与冲击伪影', '密集咳嗽 / 冲击伪影') for r in rows])
    axes[0].tick_params(axis='y', labelsize=11, pad=10)
    ax = axes[0]
    ax.set_title('参考分箱不一致率（%）\n分别与各自参考核对', loc='left', fontsize=11.5, pad=10, linespacing=1.6)
    for mode, shift in [('time', -.17), ('fixed', .17)]:
        values = [r['reference_comparison']['modes'][mode]['mismatch_percent'] for r in rows]
        ax.barh(y+shift, values, height=.27, color=COLORS[mode], zorder=2)
        for i, value in enumerate(values):
            ax.text(value+.4, i+shift, f'{value:.2f}', va='center', fontsize=10, color=COLORS[mode])
    ax.set_xlim(0, 35)
    ax.set_xticks([0, 10, 20, 30])
    for ax, values, title, ticks, limit, pad in [
        (axes[1], [r['reference_comparison']['scored_percent'] for r in rows],
         '共同核对范围（%）\n占整段记录；两方式相同', [0, 25, 50, 75, 100], 118, 1.4),
        (axes[2], [r['filter_nrmse'] for r in rows],
         '共用曲线幅值误差（%）\n相对无噪声参考的 RMSE', [0, 2, 4, 6], 8, .09),
    ]:
        ax.set_title(title, loc='left', fontsize=11.5, pad=10, linespacing=1.6)
        ax.barh(y, values, height=.42, color=COLORS['shared'], zorder=2)
        for i, value in enumerate(values):
            ax.text(value+pad, i, f'{value:.2f}', va='center', fontsize=10, color='#3B4655')
        ax.set_xlim(0, limit)
        ax.set_xticks(ticks)
    fig.legend(handles=[Patch(color=COLORS['time'], label='时间分箱（每组上条）'),
                        Patch(color=COLORS['fixed'], label='固定幅值分箱（每组下条）'),
                        Patch(color=COLORS['shared'], label='两种方式共用结果')],
               loc='upper center', bbox_to_anchor=(.57, 1.005), ncol=3, frameon=False, fontsize=11)
    out = DATA / 'figures' / 'scenario_overview.png'
    fig.savefig(out, dpi=240, facecolor='white')
    plt.close(fig)
    print(out)


if __name__ == '__main__':
    main()

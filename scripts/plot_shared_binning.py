"""Render full-minute and two-cycle detail figures from measured application results."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/measurements/shared_binning'
FONT=FontProperties(fname='/System/Library/Fonts/Hiragino Sans GB.ttc')
plt.rcParams.update({'font.family':FONT.get_name(),'font.size':8,'axes.unicode_minus':False,
    'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.5})
PALETTES={'inhale':['#b9d9ef','#8fc3e2','#60a6cf','#3485b5','#16618e'],
          'exhale':['#f8e5b5','#f2d388','#e6b95e','#ce952f','#a46c12']}
# Details intentionally show artifacts/attenuation when present, not only good breaths.
DETAIL={'motion_artifact':(200,210),'cough_artifact':(200,210),'local_cough':(199,209),
        'repeated_cough':(200,210),'apnea':(194,206),'periodic_weakening':(196,208)}


def main():
    payload=json.loads((OUT/'metrics.json').read_text());figdir=OUT/'figures';figdir.mkdir(exist_ok=True)
    for row in payload['rows']:
        sid=row['id'];d=json.loads((OUT/f'{sid}.json').read_text())
        raw=np.array(d['raw']);f=np.array(d['filtered']);clean=np.array(d['truth'])
        x=f[:,0]/50-180;valid=np.ones(len(f),bool)
        for iv in d['quality']['invalidIntervals']:valid &= ~((f[:,0]>=iv['start'])&(f[:,0]<iv['end']))
        full=(x>=0)&(x<60);lo=min(raw[full,1].min(),f[full,1].min(),clean[full].min());hi=max(raw[full,1].max(),f[full,1].max(),clean[full].max())
        ylim=(lo-(hi-lo)*.08,hi+(hi-lo)*.12)
        detail=DETAIL.get(sid,(200,200+min(16,120/row['preset']['bpm'])))
        for mode in ['time','fixed']:
            fig,axes=plt.subplots(2,1,figsize=(5.0,2.85),gridspec_kw={'height_ratios':[1,1.15]})
            fig.subplots_adjust(left=.115,right=.965,bottom=.13,top=.94,hspace=.43)
            for n,ax in enumerate(axes):
                ax.plot(x,raw[:,1],color='#a5adb8',lw=.55,zorder=1)
                ax.plot(x,clean,color='#607d66',lw=.65,alpha=.85,zorder=2)
                ax.plot(x,np.where(valid,f[:,1],np.nan),color='#2563eb',lw=1,zorder=3)
                ax.plot(x,np.where(~valid,f[:,1],np.nan),color='#bd6b32',lw=.9,ls=(0,(3,2)),zorder=3)
                if mode=='fixed':
                    for i,level in enumerate(np.linspace(*d['bounds'],6)):
                        ax.axhline(level,color='#169399',lw=.6,ls='-' if i in (0,5) else '--',alpha=.8)
                if n==1:
                    for kind,color,marker in [('peaks','#dc5960','^'),('valleys','#309b79','v')]:
                        ev=d[kind]
                        ax.scatter([p['sequence']/50-180 for p in ev],[p['value'] for p in ev],s=11,c=color,marker=marker,zorder=4)
                for b in d['bins'][mode]:
                    a,z=b['start']/50-180,b['end']/50-180
                    color=PALETTES[b['direction']][b['bin']-1]
                    ax.axvspan(a,z,ymin=0,ymax=.055,color=color,lw=0,zorder=5)
                    if mode=='time' and n==1:
                        ax.axvline(a,color=color,ls='--',lw=.45,alpha=.65)
                ax.set_ylim(*ylim);ax.grid(axis='y',alpha=.16);ax.tick_params(labelsize=8.5,pad=2)
                if n==0:
                    ax.set_xlim(0,60);ax.set_xticks([0,20,40,60]);ax.set_title('完整 60 秒',fontsize=9,loc='left',pad=2)
                else:
                    a,z=detail[0]-180,detail[1]-180
                    ax.set_xlim(a,z);ax.set_title('局部放大',fontsize=9,loc='left',pad=2)
                    # Label only comfortably sized bins in the detail panel.
                    for b in d['bins'][mode]:
                        mid=(b['start']+b['end'])/100-180
                        if a<mid<z and (b['end']-b['start'])/50>(z-a)*.035:
                            ax.text(mid,.07,str(b['bin']),transform=ax.get_xaxis_transform(),ha='center',fontsize=7,color='#344054')
                    ax.set_xlabel('记录内时间 / 秒',fontsize=9,labelpad=1)
            fig.savefig(figdir/f'{sid}_{mode}.png',dpi=230)
            plt.close(fig)
if __name__=='__main__':main()

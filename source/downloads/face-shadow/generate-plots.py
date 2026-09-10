"""Generate analytical illustrations, not measured UE results. Requires numpy/matplotlib."""
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
out=Path(sys.argv[1] if len(sys.argv)>1 else '.');out.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.size':12,'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#95a6b9','axes.labelcolor':'#37465b','text.color':'#24364b','xtick.color':'#5c6c80','ytick.color':'#5c6c80','figure.facecolor':'#f5f8fc','axes.facecolor':'#f5f8fc','svg.fonttype':'path'})
x=np.linspace(-2.5,2.5,1201)
fig,ax=plt.subplots(figsize=(10.5,4.6),layout='constrained')
ax.step(x,(x>=0).astype(float),where='post',color='#afbbc9',lw=2,label='Hard threshold')
for width,color in [(1,'#2375b9'),(1.5,'#16a39a'),(3,'#dd816c')]:
 t=np.clip((x+width/2)/width,0,1);ax.plot(x,t*t*(3-2*t),color=color,lw=2.8,label=f'Full transition: {width:g} px')
ax.set(xlabel='Screen-space position relative to the edge (px)',ylabel='Lit weight',xlim=(-2.5,2.5),ylim=(-.03,1.03),title='The transition belongs to the edge, not the whole face')
ax.grid(alpha=.18);ax.legend(loc='upper left',frameon=False,fontsize=10)
fig.savefig(out/'coverage-width.svg');fig.savefig(out/'coverage-width.png',dpi=160);plt.close(fig)
d=np.linspace(0,500,1001);factor=1-np.minimum(1,(d/1000+.8)**2)
fig,ax=plt.subplots(figsize=(10.5,4.2),layout='constrained')
ax.plot(d,factor,color='#dd816c',lw=3)
ax.axvline(200,color='#657d97',ls='--',lw=1.4)
ax.annotate('At input 200: factor = 0\n=> half-width becomes zero',xy=(200,0),xytext=(250,.20),arrowprops={'arrowstyle':'->','color':'#657d97'},fontsize=11)
ax.set(xlabel='Depth input (unit depends on the upstream mapping)',ylabel='Width multiplier',title='Early distance formula: 1 - min(1, (depth / 1000 + 0.8)^2)',xlim=(0,500),ylim=(-.018,.39));ax.grid(alpha=.18)
fig.savefig(out/'distance-weight.svg');fig.savefig(out/'distance-weight.png',dpi=160);plt.close(fig)

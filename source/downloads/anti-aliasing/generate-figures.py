"""Analytical diagrams. No game-engine render or performance measurements."""
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

out = Path(sys.argv[1]) if len(sys.argv)>1 else Path('figures')
out.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'path'})

fig, ax=plt.subplots(figsize=(10,4.7),layout='constrained')
fig.patch.set_facecolor('#f7fafc'); ax.set_facecolor('#f7fafc')
frames=np.arange(0,31)
for alpha,c in [(0.1,'#187e9c'),(0.25,'#b65139')]:
    ax.plot(frames,(1-alpha)**frames,label=f'Current-frame weight = {alpha}',color=c,lw=2.5)
ax.set(xlabel='Frames elapsed',ylabel='Fraction of an existing history contribution',ylim=(0,1.04),xlim=(0,30))
ax.set_title('History fades exponentially',loc='left',fontsize=18,pad=16)
ax.grid(alpha=.15);ax.spines[['top','right']].set_visible(False);ax.legend(frameon=False)
fig.savefig(out/'history-decay.svg');fig.savefig(out/'history-decay.png',dpi=160);plt.close(fig)

# A straight edge y = .57*x + 2.1; 4x uses a 2x2 educational sample grid.
# The dense panel estimates area with 64x64 samples per pixel.
fig=plt.figure(figsize=(12,6.3),facecolor='#122237')
fig.text(.06,.87,'REAL-TIME',color='#77d9d2',fontsize=15,weight='bold')
fig.text(.06,.77,'ANTI-ALIASING',color='white',fontsize=33,weight='bold')
fig.text(.06,.69,'Samples, history and edge reconstruction',color='#b6c7dc',fontsize=14)
for idx,(samples,label) in enumerate([(1,'ONE SAMPLE'),(2,'4-SAMPLE COVERAGE'),(64,'DENSE AREA ESTIMATE')]):
 ax=fig.add_axes([.065+idx*.312,.17,.265,.43])
 offsets=(np.arange(samples)+.5)/samples
 x=np.arange(8)[None,:,None,None]+offsets[None,None,None,:]
 y=np.arange(8)[:,None,None,None]+offsets[None,None,:,None]
 coverage=(y < .57*x+2.1).mean(axis=(2,3))
 bg=np.array([.12,.20,.31]); fg=np.array([.40,.86,.82])
 rgb=bg[None,None,:]*(1-coverage[:,:,None])+fg[None,None,:]*coverage[:,:,None]
 ax.imshow(rgb,origin='lower',interpolation='nearest',extent=[0,8,0,8])
 ax.set_xticks(np.arange(9));ax.set_yticks(np.arange(9));ax.grid(color='#93b0c4',alpha=.25,lw=.5)
 ax.tick_params(left=False,bottom=False,labelleft=False,labelbottom=False)
 for spine in ax.spines.values():spine.set_visible(False)
 ax.set_title(label,color='#dbeaf4',fontsize=10,pad=12)
fig.text(.06,.06,'BYTIVOR  /  RENDERING NOTES',color='#87a5bb',fontsize=11)
fig.savefig(out/'cover.svg');fig.savefig(out/'cover.png',dpi=140);plt.close(fig)
for f in out.glob('*.svg'):
 f.write_text('\n'.join(line.rstrip() for line in f.read_text().splitlines())+'\n')
print('Generated analytical cover and history-weight curve.')

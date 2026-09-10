from pathlib import Path
import os, argparse
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch
parser=argparse.ArgumentParser(); parser.add_argument('--out',default='generated'); args=parser.parse_args()
ROOT=Path(args.out); OUT=ROOT/'figures'; TEX=ROOT/'textures'
OUT.mkdir(parents=True,exist_ok=True); TEX.mkdir(parents=True,exist_ok=True)
font_path=os.environ.get('HOSIERY_FONT','/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
font=FontProperties(fname=font_path)
plt.rcParams.update({'font.family':font.get_name(),'font.size':12,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'#f6f9fd','axes.facecolor':'#f6f9fd','text.color':'#182d46','axes.labelcolor':'#182d46','savefig.bbox':'tight'})
# Register the actual font for reproducibility on this machine.
from matplotlib import font_manager
font_manager.fontManager.addfont(font.get_file())
def save(name,fig):
 fig.savefig(OUT/name,dpi=145); plt.close(fig)
def box(ax,x,y,w,h,t,c='#dcecf7'):
 ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.015,rounding_size=.025',fc=c,ec='#a9bdd1',lw=1))
 ax.text(x+w/2,y+h/2,t,ha='center',va='center',fontsize=12)
def arrow(ax,a,b): ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'->','color':'#408ea5','lw':2})
fig,ax=plt.subplots(figsize=(12,5)); ax.set(xlim=(0,1),ylim=(0,1)); ax.axis('off')
ax.text(.02,.94,'UE HOSIERY / 从结构决定管线',fontsize=24,weight='bold')
for i,(a,b,c) in enumerate([('贴紧皮肤 / 细织物','Opaque 身体合成','稳定深度、阴影、速度'),('可见网孔 / 蕾丝','Masked 袜壳 + 皮肤','几何孔洞、独立覆盖'),('离肤薄纱 / 悬空布片','Translucent / 分层方案','透射、排序、性能预算')]):
 y=.64-i*.25;box(ax,.03,y,.25,.17,a);box(ax,.37,y,.28,.17,b);box(ax,.74,y,.23,.17,c);arrow(ax,(.29,y+.085),(.36,y+.085));arrow(ax,(.66,y+.085),(.73,y+.085))
save('pipeline.png',fig)
# All periodic textures are sampled at pixel centres. 8 knit loops per tile.
n=1024; u,v=np.meshgrid((np.arange(n)+.5)/n,(np.arange(n)+.5)/n)
x=u*8; y=v*8
# Sinuous paired strands: an illustrative loop-like knit, not a measured stitch scan.
phase=np.sin(y*2*np.pi)*.24
p=(x+phase)%1
strand=np.minimum(p,1-p)
knit=np.exp(-(strand/.095)**4)
height=knit*(.65+.35*np.cos(y*2*np.pi)**2)
rough=.42+.22*(1-height)
density=.7+.3*knit
angle=np.arctan2(np.ones_like(x),-1.5*np.cos(y*2*np.pi))
flow=np.stack((np.cos(angle)*.5+.5,np.sin(angle)*.5+.5,np.zeros_like(x)),2)
# UV-space slopes, authored as an illustrative DirectX-style tangent normal; check target UV convention on import.
dhdy,dhdx=np.gradient(height)
norm=np.stack((-dhdx*9,dhdy*9,np.ones_like(x)),2);norm/=np.linalg.norm(norm,axis=2,keepdims=True)
net=(np.minimum((u*8+v*8)%1,1-(u*8+v*8)%1)<.08)|(np.minimum((u*8-v*8)%1,1-(u*8-v*8)%1)<.08)
# Tileable floral rosettes + connector filaments, an original schematic lace coverage.
cx=np.sin(u*2*np.pi*4);cy=np.sin(v*2*np.pi*4)
r=np.sqrt(cx*cx+cy*cy);theta=np.arctan2(cy,cx)
lace=(np.abs(r-(.63+.16*np.cos(6*theta)))<.09)|(np.abs(cx)<.045)|(np.abs(cy)<.045)
# Reinforcement is intentionally non-tiling along V.
reinforce=np.clip((v-.82)/.05,0,1)+np.clip((.12-v)/.04,0,1)
reinforce=np.clip(reinforce,0,1)
images={'T_Knit_Coverage':knit,'T_Knit_Density':density,'T_Knit_Roughness':rough,'T_Knit_Normal':norm*.5+.5,'T_Knit_Flow':flow,'T_Fishnet_Coverage':net.astype(float),'T_Lace_Coverage':lace.astype(float),'T_Reinforcement':reinforce}
for name,a in images.items(): Image.fromarray(np.uint8(np.clip(a,0,1)*255+.5)).save(TEX/(name+'.png'))
fig,axs=plt.subplots(2,4,figsize=(13,6))
for ax,(name,a) in zip(axs.flat,images.items()):
 ax.imshow(a if a.ndim==3 else a,cmap='gray',vmin=0,vmax=1);ax.axis('off');ax.set_title(name.replace('T_','').replace('_',' / '),fontsize=11)
fig.suptitle('贴图通道图谱 / 1024² 原创程序纹理',fontsize=22);fig.tight_layout();save('channels.png',fig)
# Radiometric transmittance curve, no artistic Fresnel added.
fig,axs=plt.subplots(1,2,figsize=(12,4.5));theta=np.linspace(0,89,400);mu=np.maximum(np.cos(np.deg2rad(theta)),.15)
for tau in [.15,.45,1.2]: axs[0].plot(theta,(1-.8)+.8*np.exp(-tau/mu),label=f'τ = {tau}')
axs[0].set(xlabel='视线与法线夹角 / °',ylabel='有效透射率',ylim=(0,1),title='覆盖 C = 0.8：厚度路径项');axs[0].legend()
for c in [.25,.6,1]: axs[1].plot(theta,1-c+c*np.exp(-.45/mu),label=f'C = {c}')
axs[1].set(xlabel='视线与法线夹角 / °',ylabel='有效透射率',ylim=(0,1),title='光学厚度 τ = 0.45：覆盖项');axs[1].legend();fig.tight_layout();save('transmission.png',fig)
# Cross-section schematic.
fig,ax=plt.subplots(figsize=(12,3.8));ax.set(xlim=(0,10),ylim=(0,3));ax.axis('off')
ax.fill_between([.2,9.8],.25,1,color='#cf9f8e');ax.text(5,.57,'皮肤：提供底色、法线与自身的光照',ha='center')
for k in range(9): ax.add_patch(plt.Circle((.8+k,1.62),.24,fc='#20314a'))
ax.text(5,2.55,'覆盖 C ≠ 光学厚度 τ ≠ 高光强度',ha='center',fontsize=22)
arrow(ax,(1.3,2.35),(1.3,1.06));arrow(ax,(4.3,2.35),(3.82,1.67));arrow(ax,(3.82,1.67),(3.1,2.32));ax.text(6,1.95,'孔隙透过 / 纱线吸收 / 表面反射',fontsize=12)
save('cross-section.png',fig)
# Analytic material patches rendered on cylindrical normals. Explicitly NOT Unreal output.
H,W=430,200;xx,yy=np.meshgrid(np.linspace(-.97,.97,W),np.linspace(0,1,H));zz=np.sqrt(1-xx*xx);NN=np.stack([xx,np.zeros_like(xx),zz],-1);L=np.array([-.5,.5,.707]);L/=np.linalg.norm(L);HH=L+np.array([0,0,1]);HH/=np.linalg.norm(HH)
ndotl=np.clip(NN@L,0,1);ndoth=np.clip(NN@HH,0,1)
configs=[('薄透黑',.65,.28,[.016,.02,.027],.44),('薄透肤',.6,.2,[.5,.29,.19],.5),('半透白',.8,.55,[.78,.8,.85],.62),('厚织黑',1,3,[.018,.023,.029],.8),('光泽黑',.8,.8,[.01,.013,.02],.23),('菱形网',.85,.5,[.018,.02,.025],.5)]
fig,axs=plt.subplots(1,6,figsize=(13,5.3))
for ax,(label,c,tau,col,rgh) in zip(axs,configs):
 trans=1-c+c*np.exp(-tau/np.maximum(zz,.15));skin=np.array([.5,.29,.21]);color=skin*trans[...,None]+np.array(col)*(1-trans[...,None])
 if label=='菱形网':
  pu=(np.arcsin(xx)/np.pi+.5)*12;pv=yy*22
  mask=(np.minimum((pu+pv)%1,1-(pu+pv)%1)<.06)|(np.minimum((pu-pv)%1,1-(pu-pv)%1)<.06)
  color=np.where(mask[...,None],np.array(col),skin)
 spec=ndoth**(2/max(rgh*rgh,.02))*.22
 rgb=np.clip(color*(.3+.7*ndotl[...,None])+spec[...,None],0,1)**(1/2.2)
 ax.imshow(rgb);ax.axis('off');ax.set_title(label,fontsize=15)
fig.suptitle('材质变量对照 / 同一解析圆柱、同一光照',fontsize=23);fig.text(.5,.01,'程序着色示意 · 用于比较参数作用，不是 UE 运行截图',ha='center',fontsize=12);save('material-study.png',fig)
# Aliasing example compare point sampled to accurate box integral for stripe union.
def integ(t,d):
 k=np.floor(t);return k*d+np.minimum(t-k,d)
def avg(t,w,d): return (integ(t+w/2,d)-integ(t-w/2,d))/w
fig,axs=plt.subplots(2,3,figsize=(12,6));q=(np.arange(192)+.5)/192
for col,f in enumerate([20,90,210]):
 a,b=np.meshgrid(q*f,q*f)
 point=((a%1)<.16)|((b%1)<.16)
 A=avg(a,f/192,.16);B=avg(b,f/192,.16);filtered=1-(1-A)*(1-B)
 for row,z in enumerate([point,filtered]):
  axs[row,col].imshow(z,cmap='gray',vmin=0,vmax=1,interpolation='nearest');axs[row,col].axis('off');axs[row,col].set_title(f'{f} 周期 / 192 像素 · '+('点采样' if row==0 else '轴向矩形面积积分'),fontsize=12)
fig.suptitle('先过滤材质，再交给时间抗锯齿',fontsize=22);fig.tight_layout();save('filtering.png',fig)
fig,axs=plt.subplots(1,3,figsize=(12,4));X,Y=np.meshgrid(np.linspace(-1,1,300),np.linspace(-1,1,300))
for ax,angledeg in zip(axs,[0,45,90]):
 a=np.deg2rad(angledeg);s=X*np.cos(a)+Y*np.sin(a);t=-X*np.sin(a)+Y*np.cos(a);z=np.exp(-(s*s/.42**2+t*t/.12**2))
 ax.imshow(z,cmap='magma',origin='lower');ax.axis('off');ax.set_title(f'方向旋转 {angledeg}°')
fig.suptitle('方向场决定高光朝向 / 椭圆瓣示意，不是 BRDF 测量',fontsize=19);fig.tight_layout();save('tangent.png',fig)
fig,ax=plt.subplots(figsize=(12,6));ax.axis('off');ax.set(xlim=(0,1),ylim=(0,1))
ax.text(.02,.95,'M_Hosiery_Opaque / 接线地图',fontsize=24)
rows=[('SkinColor + YarnColor','Coverage + TauRGB','MF_HosieryColor → Base Color'),('MacroNormalWS + ViewWS','Density / Reinforcement','角度路径项（不接 Opacity）'),('Roughness + KnitNormal','NormalStrength','Roughness / Normal'),('Flow RG → Decode / Normalize','TransformVector → Tangent','Anisotropy / Tangent')]
for i,(a,b,c) in enumerate(rows):
 y=.7-i*.21;box(ax,.02,y,.27,.14,a);box(ax,.34,y,.27,.14,b);box(ax,.67,y,.31,.14,c);arrow(ax,(.29,y+.07),(.33,y+.07));arrow(ax,(.61,y+.07),(.665,y+.07))
save('wiring.png',fig)
print('Generated 8 figures and',len(images),'textures')

// Original technical diagrams and numerical plots. No character render is simulated.
const fs=require('node:fs'),path=require('node:path');
const m=require('../source/downloads/character-lab/math-reference.cjs');
const out=path.join(__dirname,'../source/img/character-lab');
const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');
const text=(x,y,s,size=20,c='#26344b')=>'<text x="'+x+'" y="'+y+'" font-size="'+size+'" fill="'+c+'">'+esc(s)+'</text>';
const rect=(x,y,w,h,c='#f3f6fb',stroke='#d9e1ee')=>'<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="10" fill="'+c+'" stroke="'+stroke+'"/>';
const line=(x,y,x2,y2,c='#bac6d9',width=2)=>'<path d="M'+x+' '+y+'L'+x2+' '+y2+'" stroke="'+c+'" stroke-width="'+width+'" fill="none"/>';
const arrow=(x,y,x2,y2)=>line(x,y,x2,y2,'#8395b1',2).replace('/>',' marker-end="url(#arr)"/>');
function save(name,title,desc,h,body){
  fs.writeFileSync(path.join(out,name),'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 '+h+'" role="img" aria-labelledby="title desc"><title id="title">'+esc(title)+'</title><desc id="desc">'+esc(desc)+'</desc><defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="#8395b1"/></marker></defs><rect width="1100" height="'+h+'" fill="#fff"/><g font-family="system-ui, -apple-system, PingFang SC, Microsoft YaHei, sans-serif">'+text(40,48,title,27)+text(40,80,desc,16,'#63728a')+body+'</g></svg>');
}
let b='';
const rows=[
['BaseColor','RGB','固有色','颜色采样 → 线性计算','#8f76c4'],
['LightMap','R / G / B','明暗偏移 / 漫反射遮蔽 / 高光 Mask','数值纹理 · sRGB OFF','#3894b2'],
['PBRMask','R / G / B / A','金属 / 光滑 / 遮蔽 / 混合','Roughness = 1 − G','#427bb4'],
['Ramp','RGB','皮肤明暗过渡的颜色','按区域选择 Face / Body','#b86c88'],
['Normal','RGB','切线空间法线','解码 → Tangent to World','#7e79b9'],
['VertexColor','A / B','描边宽度 / 沿相机前向偏移','顶点阶段数据','#428b7b']
];
rows.forEach((r,i)=>{let y=110+i*83;b+=rect(40,y,1020,70);b+=rect(52,y+10,155,50,r[4],r[4]);b+=text(65,y+42,r[0],19,'#fff')+text(225,y+30,r[1],17)+text(380,y+30,r[2],19)+text(380,y+55,r[3],16,'#63728a');});
save('channel-contract.svg','01 / 贴图通道契约','本文的 UE 资产约定；非官方游戏贴图解码结果。',635,b);
b='';
const stages=[
['角色资产','颜色 / Mask / 法线 / 顶点色','先检查色彩空间和通道'],
['Surface · Unlit','漫反射 + GGX / BP + Emission','主光由原型 MPC 显式传入'],
['OutlineMesh','Leader Pose → WPO 外壳','骨骼匹配 · 背面保留'],
['Post Process','SceneDepth / Stencil → Rim','按可见性合成轮廓亮边'],
['画面输出','Bloom / 色调映射 / 时序处理','具体顺序取决于插入位置']
];
stages.forEach((r,i)=>{let y=112+i*92;b+=rect(175,y,750,70,i===1?'#edf5fc':'#f3f6fb');b+=text(199,y+31,r[0],21)+text(424,y+29,r[1],19)+text(424,y+54,r[2],16,'#63728a');if(i<4)b+=arrow(550,y+72,550,y+89);});
save('ue-workflow.svg','02 / 从 Unity 效果到 UE 接入位置','讲解顺序与 GPU 绘制顺序不同：描边几何先进入场景，再进行深度边缘光。',595,b);
function axes(x,y,w,h,xmin,xmax,xlabel,ylabel){
 let s='';
 for(let t=0;t<=4;t++){let py=y+h-h*t/4;s+=line(x,py,x+w,py,'#e6ebf3',1)+text(x-42,py+5,(t/4).toFixed(2),15,'#65758c');}
 for(let t=0;t<=4;t++){let px=x+w*t/4;s+=text(px-15,y+h+25,(xmin+(xmax-xmin)*t/4).toFixed(1),15,'#65758c');}
 return s+line(x,y,x,y+h)+line(x,y+h,x+w,y+h)+text(x,y-18,ylabel,16,'#63728a')+text(x+w/2-38,y+h+54,xlabel,17);
}
function curve(x,y,w,h,xmin,xmax,fn,color){
 let pts=[];for(let i=0;i<=240;i++){let t=i/240,value=fn(xmin+(xmax-xmin)*t);pts.push((x+w*t).toFixed(2)+','+(y+h-h*Math.max(0,Math.min(1,value))).toFixed(2));}
 return '<polyline points="'+pts.join(' ')+'" fill="none" stroke="'+color+'" stroke-width="3"/>';
}
b=axes(100,145,900,300,-1,1,'有符号 N·L','亮面权重 w');
const dc=[['k = 6','#399caa',6,0],['k = 12','#567acc',12,0],['k = 24','#a46cba',24,0],['k = 12, Offset = +0.25','#bd7446',12,.25]];
dc.forEach((r,i)=>{b+=curve(100,145,900,300,-1,1,x=>m.diffuse(x,r[3],0,r[2]),r[1]);let x=100+i*245;b+=line(x,538,x+24,538,r[1],4)+text(x+32,544,r[0],17);});
save('diffuse-curves.svg','03 / 明暗边界如何移动','数值模型：w = 1 / (1 + 2^(−k·(N·L + Offset)))，Center = 0。',575,b);
b=axes(80,155,420,285,0,60,'H 与 N 的夹角 °','Blinn-Phong：峰值 = 1');
b+=axes(640,155,400,285,0,60,'H 与 N 的夹角 °','GGX D：各自除以峰值');
[[16,'#399caa'],[48,'#567acc'],[96,'#a46cba']].forEach((r,i)=>{b+=curve(80,155,420,285,0,60,a=>Math.cos(a*Math.PI/180)**r[0],r[1]);b+=line(90+i*135,525,108+i*135,525,r[1],4)+text(115+i*135,531,'p = '+r[0],17);});
[[.25,'#399caa'],[.45,'#567acc'],[.7,'#a46cba']].forEach((r,i)=>{b+=curve(640,155,400,285,0,60,a=>m.distribution(Math.cos(a*Math.PI/180),r[0])/m.distribution(1,r[0]),r[1]);b+=line(643+i*135,525,661+i*135,525,r[1],4)+text(668+i*135,531,'r = '+r[0],17);});
save('specular-curves.svg','04 / 两种高光的形状控制','右图归一化仅用于比较宽度；它没有表达实际 BRDF 强度，也不是角色渲染结果。',575,b);
b=text(50,127,'屏幕上的一行像素',19)+rect(50,150,580,100,'#e0e9f7')+rect(630,150,420,100,'#f1eef8');
b+=text(205,191,'角色可见表面',22)+text(218,224,'深度 300 cm',18)+text(746,191,'更远的背景',22)+text(755,224,'深度 1000 cm',18);
b+='<circle cx="584" cy="201" r="12" fill="#e07f55"/><circle cx="701" cy="201" r="10" fill="#8562bc"/>';
b+=arrow(584,264,701,264)+text(550,300,'偏移采样',17);
b+=rect(50,333,485,168)+text(72,368,'中心留在角色上',23)+text(72,405,'d0 = 300，dR = 1000',21)+text(72,440,'gap = (1000 − 300) / 300 ≈ 2.33',19)+text(72,476,'超过阈值 → 内侧亮边',20,'#8b5faf');
b+=rect(559,333,491,168)+text(582,368,'还要通过可见性检查',23)+text(582,405,'Stencil == 7',21)+text(582,439,'CustomDepth ≈ SceneDepth',21)+text(582,476,'否则 Mask = 0，避免角色穿墙发光',18);
save('depth-rim.svg','05 / 深度断层 → 屏幕空间边缘光','正的线性视空间深度；四个方向取最大断层，不累加角点亮度。',545,b);
b=rect(40,113,485,370);
b+='<circle cx="278" cy="281" r="122" fill="#303852"/><circle cx="278" cy="281" r="105" fill="#cbd8eb"/>';
b+=text(195,278,'主体网格',23)+text(188,310,'遮挡壳内部',20);
b+=arrow(145,160,185,185)+text(62,149,'膨胀外壳',18)+arrow(349,397,397,444)+text(270,467,'可见线条 = 壳的背面',18);
b+=rect(554,113,506,170)+text(579,150,'VertexColor.A → 宽度',23)+text(579,189,'0：无膨胀；1：完整 WidthCM',19)+text(579,232,'宽度单位是 cm，透视自然影响远近',18);
b+=rect(554,307,506,176)+text(579,345,'VertexColor.B → 深度偏移',23)+text(579,383,'nz = DepthBias × (1 − B)',21)+text(579,424,'B = 1 取消深度偏移，不等于取消描边',18)+text(579,459,'平面分量来自法线在 Camera R / U 的投影',17);
save('outline-shell.svg','06 / 反向外壳与顶点色控制','示意为几何截面；UE 原型用额外骨骼网格、WPO 和背面 Mask 实现。',530,b);
console.log('Generated 6 original UE workflow diagrams and numeric plots.');

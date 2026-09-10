"""Original explanatory figures. Python standard library only; no game assets."""
from pathlib import Path
import math, struct, zlib, base64, html

SCRIPT = Path(__file__).resolve()
OUT = (SCRIPT.parents[1] / 'source/img/toon-pipeline'
       if SCRIPT.parent.name == 'tools' else Path.cwd() / 'toon-figures')
OUT.mkdir(parents=True, exist_ok=True)
INK, BLUE, MUTED = '#253552', '#49b1f5', '#70829a'
def txt(x,y,s,size=20,color=INK,weight=400):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}">{html.escape(s)}</text>'
def rect(x,y,w,h,c='#edf6ff',stroke='none'):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{c}" stroke="{stroke}"/>'
def line(x1,y1,x2,y2,c=BLUE,arrow=False):
    return f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{c}" stroke-width="2.5" fill="none"'+(' marker-end="url(#arrow)"' if arrow else '')+'/>'
def svg(name,title,sub,body,h=520):
    text=f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="{h}" viewBox="0 0 1080 {h}" role="img" aria-labelledby="title desc"><title id="title">{html.escape(title)}</title><desc id="desc">{html.escape(sub)}</desc><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10" fill="{BLUE}"/></marker></defs><rect width="1080" height="{h}" rx="20" fill="#f8fbff"/><g font-family="-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif">{txt(38,49,title,29,INK,650)}{txt(38,83,sub,16,MUTED)}{body}{txt(38,h-22,'BYTIVOR / TECHNICAL NOTES · 原创原理示意',13,MUTED)}</g></svg>'''
    (OUT/name).write_text(text)
def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a))); return t*t*(3-2*t)
def norm(v):
    n=math.sqrt(sum(x*x for x in v)); return tuple(x/n for x in v)
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def png(mode,n=240):
    L=norm((-.65,.45,.65)); H=norm((L[0],L[1],L[2]+1)); data=bytearray()
    for py in range(n):
        data.append(0)
        for px in range(n):
            x=(px+.5-n/2)/(n*.46); y=-(py+.5-n/2)/(n*.46); r=x*x+y*y
            if r>1:
                data.extend((0,0,0,0)); continue
            z=math.sqrt(1-r); N=(x,y,z); h=.5*dot(N,L)+.5
            q=smooth(.54,.58,h); vis=smooth(-.04,.04,x+.18)
            dark=(.07,.14,.32); light=(.4,.65,.95)
            if mode=='normal': c=tuple(v*.5+.5 for v in N)
            elif mode=='depth': c=(.25+.7*z,)*3
            elif mode=='base': c=light
            elif mode=='q': c=(q,)*3
            elif mode=='vis': c=(vis,)*3
            else:
                w=max(0,dot(N,L)) if mode=='lambert' else q
                if mode=='combined': w=q*vis
                c=tuple(a+(b-a)*w for a,b in zip(dark,light))
                if mode=='final':
                    spec=smooth(.65,.75,max(0,dot(N,H))**48)*q
                    c=tuple(min(1,v+.30*spec) for v in c)
                    if r>.94: c=(.025,.035,.065)
            # normal/depth/masks are data visualizations; colors are linear->sRGB.
            if mode not in ('normal','depth','q','vis'):
                c=tuple(12.92*v if v<=.0031308 else 1.055*v**(1/2.4)-.055 for v in c)
            data.extend((*[round(max(0,min(1,v))*255) for v in c],255))
    def chunk(k,v): return struct.pack('!I',len(v))+k+v+struct.pack('!I',zlib.crc32(k+v)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',n,n,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(bytes(data),9))+chunk(b'IEND',b'')
def sphere(x,y,mode,w=240):
    encoded=base64.b64encode(png(mode)).decode()
    return f'<image x="{x}" y="{y}" width="{w}" height="{w}" href="data:image/png;base64,{encoded}"/>'

body=''
for i,(mode,title,sub) in enumerate([('lambert','01 连续漫反射','光照变化连续'),('toon','02 明暗分层','保留亮 / 暗两块颜色'),('final','03 高光与轮廓','独立添加高光和外轮廓')]):
    x=38+i*350; body+=rect(x,115,330,365,'#fff')+sphere(x+45,133,mode)+txt(x+24,404,title,22,INK,600)+txt(x+24,440,sub,17,MUTED)
svg('stages.svg','卡通渲染：从连续光照到可控色块','同一解析球体、同一光源与相机。CPU 公式示意，并非 UE 或游戏截图。',body,540)

body=''
nodes=[('材质与模型','BaseColor / Normal / Toon 参数'),('Base Pass','写入 GBuffer + 深度'),('Lighting','读取属性，计算风格化光照'),('合成与后处理','描边 / 时域处理 / 色调映射')]
for i,(a,b) in enumerate(nodes):
    y=114+i*105; body+=rect(265,y,530,77,'#fff', '#dceaf8')+txt(287,y+30,a,23,INK,600)+txt(287,y+59,b,17,MUTED)
    if i<3: body+=line(530,y+77,530,y+100,arrow=True)
body+=rect(35,317,200,94,'#e7f3ff')+txt(52,348,'Shadow Pass',22)+txt(52,378,'提供可见性 V',18)+line(235,361,258,361,arrow=True)
body+=rect(825,317,220,94,'#f2ecff')+txt(843,348,'Ramp Atlas',22)+txt(843,378,'颜色 / 风格查找表',17)+line(825,361,802,361,arrow=True)
svg('pipeline.svg','01 / 一帧里的卡通渲染数据流','逻辑依赖图：省略引擎中可并行、可选及分支 Pass，不代表所有 UE 版本的固定执行顺序。',body,590)

body=''
for i,(mode,a,b) in enumerate([('base','Base Color','线性颜色'),('normal','Normal','编码后的方向'),('depth','Depth','近处更亮，仅为示意'),('q','Toon Data','阈值等自定义参数')]):
    x=30+i*264;body+=rect(x,120,246,306,'#fff')+sphere(x+28,132,mode,190)+txt(x+18,358,a,23,INK,600)+txt(x+18,393,b,16,MUTED)
body+=txt(38,469,'屏幕上同一位置 → 读取多张纹理 → 还原表面属性 → 决定如何着色',21)
svg('gbuffer.svg','02 / 先记录表面，再计算光照','逻辑属性可视化；并非 UE 实际通道布局。Toon Data 面板用明暗权重帮助理解数据。',body,530)

body=rect(35,115,630,325,'#fff')
for t in [0,.25,.5,.75,1]:
    x=85+t*530; y=394-t*238
    body+=line(x,142,x,394,'#e5edf6')+txt(x-8,421,str(t),14,MUTED)
    body+=line(85,y,615,y,'#e5edf6')
for label,col,func in [('half-Lambert','#a7b6c7',lambda x:x),('step','#a58add',lambda x:float(x>=.56)),('smoothstep','#49b1f5',lambda x:smooth(.48,.64,x))]:
    pts=' '.join(f'{85+i/240*530:.2f},{394-func(i/240)*238:.2f}' for i in range(241))
    body+=f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="3"/>'
body+=txt(78,139,'输出权重',16,MUTED)+txt(563,467,'h →',18,MUTED)
body+=txt(710,162,'阈值 t = 0.56',24,INK,600)+txt(710,202,'软边宽度 s = 0.08',20)+txt(710,253,'灰：连续输入',18,'#8a9caf')+txt(710,290,'紫：硬阈值',18,'#a58add')+txt(710,327,'蓝：有过渡的阈值',18,BLUE)+txt(710,388,'越窄越锐利，也越易闪烁',18,MUTED)
svg('threshold.svg','03 / 色块边界由阈值函数决定','s 是阈值两侧的半宽；完整过渡区间为 [t − s, t + s]。',body,530)

body=''
for i,(mode,a,b) in enumerate([('q','Q：形体分层','只由法线和光向决定'),('vis','V：投影可见性','演示遮挡物形成的一条阴影'),('combined','Q × V：合并','只在共同允许的位置进入亮色')]):
    x=38+i*350;body+=rect(x,115,330,365,'#fff')+sphere(x+45,130,mode)+txt(x+22,405,a,22,INK,600)+txt(x+22,441,b,16,MUTED)
svg('shadow.svg','04 / 形体明暗 ≠ 遮挡阴影','前两个面板为权重，白 = 1，黑 = 0；第三个面板为最终线性颜色的 sRGB 显示。',body,540)

body=''
palettes=[('#25345e','#9ed4ff'),('#733e64','#ffd3cf'),('#304e4b','#c7ebc7')]
for i,(a,b) in enumerate(palettes):
    y=155+i*76;body+=rect(210,y,500,52,a)+f'<rect x="460" y="{y}" width="250" height="52" fill="{b}"/>'+txt(40,y+33,f'row {i}',23)+line(715,y+26,766,y+26,arrow=True)+txt(790,y+33,f'v = {i+.5} / 3',22)
body+=line(210,395,710,395,arrow=True)+txt(300,433,'u：暗色 ← 光照坐标 → 亮色',20)
body+=txt(40,483,'每一行是一套风格；取行中心，避免把邻行颜色一起插值。',19,MUTED)
svg('ramp.svg','05 / Ramp Atlas：把美术风格变成可寻址的数据','示意图使用三行两段式 Ramp。实际可使用平滑颜色曲线与多级阴影。',body,550)

body=''
for x,title,lines in [(38,'深度边缘',['找到轮廓、遮挡交界','线性深度差 / 中心深度','防止距离变化放大阈值误差']),(390,'法线边缘',['找到折角、内部结构','1 − dot(N₀, Nᵢ)','需要抑制细碎法线纹理']),(742,'选择与合成',['材质 ID / Stencil 限定对象','合并边缘后再上色','按实际 RT 尺寸计算采样偏移'])]:
    body+=rect(x,140,300,290,'#fff','#dceaf8')+txt(x+20,187,title,26,INK,600)
    for j,s in enumerate(lines):body+=txt(x+20,244+j*58,s,17,MUTED)
svg('outline.svg','06 / 描边不是把所有变化都画黑','边缘检测负责找变化；材质掩码、阈值和采样半径决定哪些变化值得保留。',body,500)
print(f'Generated {len(list(OUT.glob("*.svg")))} original figures.')

---
title: UE 卡通角色渲染：贴图、光照与描边实解
date: 2021-11-12 14:30:00
permalink: 2026/09/10/ue-toon-character-lab/
demo_views: 153
demo_likes: 6
updated: 2026-09-10 16:59:51
categories: 卡通渲染
tags: [Unreal Engine, 角色渲染, 材质, HLSL, 战双风格]
cover: /img/pgr-reference/image-23.png
description: 从角色贴图通道出发，依次拆解分段漫反射、GGX 与 Blinn-Phong 高光、深度边缘光和几何描边，附 UE 材质接法与 HLSL。
toc: true
---

卡通角色的质感来自多个层次的共同配合：漫反射维持干净的明暗块面，高光区分头发、布料与金属，边缘光和描边则帮助轮廓从背景中分离。只调其中一项，往往会出现局部好看、整体却不协调的情况。

这篇文章围绕 UE5 的角色材质搭建展开，按 **贴图分析 → 漫反射 → PBR 高光 → Blinn-Phong 高光 → 边缘光 → 描边 → 最后效果** 的顺序，拆开观察每一层，再把它们放回同一套材质流程。每个环节都给出通道约定、节点接法和 HLSL，让调整有明确的落点。

<figure class="reference-figure"><img src="/img/pgr-reference/image-23.png" alt="最终效果：角色正面" loading="lazy"><figcaption>最终效果：角色正面</figcaption></figure>

<!-- more -->

## 一、贴图分析

### 1.1 先看每个通道在角色上的位置

先把贴图通道单独输出到角色上。这一步很关键：RGB 合在一起只是一张彩色数据图，拆开后才看得出哪些区域参与明暗偏移，哪些区域允许高光，以及哪些面部位置需要收窄描边。

<figure class="reference-figure"><img src="/img/pgr-reference/channel-overview.svg" alt="BaseColor、LightMap、顶点色、PBRMask、Normal 与 Ramp 通道总览" loading="lazy"><figcaption>BaseColor、LightMap、顶点色、PBRMask、Normal 与 Ramp 通道总览；右下角为 Body SSS Ramp 颜色示意</figcaption></figure>

右下角 Body SSS Ramp 用来说明皮肤从暗部到亮部的颜色过渡；接入材质时，需要另行制作对应的 Ramp 纹理。

这张图是**通道作用的模型预览拼图**，不是可直接导入 UE 的 UV 贴图集。截取其中的人物轮廓，也不会得到模型对应的贴图。真正接入同一角色仍需要与模型 UV 对应的原始纹理和顶点数据；本文没有提供原游戏模型或完整资产包。

| 数据 | 数据含义 | UE 接入含义 |
| --- | --- | --- |
| BaseColor RGB | 固有色 | 颜色纹理，通常开启 sRGB |
| LightMap R | Ramp 偏移 | 控制明暗分界，值越大越容易进入亮面 |
| LightMap G | 固有阴影 AO | 控制漫反射受光权重 |
| LightMap B | SpecularMask / PBR 区域控制 | 本文明确用作总高光许可 |
| PBRMask R | Metallic | 金属度 |
| PBRMask G | Smoothness | 经过 OneMinus 得到 Roughness |
| PBRMask B | 高光 AO | 遮蔽高光 |
| PBRMask A | PBR 倾向 | 在 Blinn-Phong 与 GGX 之间 Lerp |
| VertexColor A | 描边粗细 | 乘外扩宽度，并屏蔽不需要的壳面 |
| VertexColor B | 面部、头发描边控制 | 控制相机深度方向的偏移 |
| Ramp | 模拟皮肤 SSS 的颜色变化 | 面部和身体皮肤分别采样 |
| Normal | PBR 表面方向 | 正确解码后转换至世界空间 |

**通道约定需要统一**：本篇 R 保留金属度，A 专门混合高光。若手上的资产采用另一种编码，应修改解码层，而不是让材质同时依赖两种说法。

### 1.2 UE 中先搭一个可以逐项观察的材质

本篇采用 UE5 传统材质路径：主材质设为 **Surface / Opaque / Unlit**，手工计算后的颜色接 Emissive。把头发、面部、身体皮肤和衣服分成材质实例，便于独立调整 Ramp 与高光。此方案需要显式传入主光方向；它不会自动获得 UE 的光源遍历、阴影和间接照明。

设置一份主光参数集合，传入表面指向光源的 `KeyLightDirection`、线性光色和归一化的 `KeyIntensity`。若从 Directional Light Actor 获取 Forward Vector，应取反后作为表面到光的方向。这里的强度是美术倍率，不直接对应灯光面板中的 lux。

贴图使用 Texture Sample Parameter 采样，在节点外把通道分好，再送给 Custom 节点。数值 Mask 关闭 sRGB，并确认压缩保留 Alpha；Normal 使用 Normalmap 采样方式；彩色 Ramp 的 sRGB 设置与制作空间保持一致，寻址设为 Clamp。纹理在材质节点中完成采样，Custom 节点接收采样结果，并按下文建立具名输入与输出类型。

先把 BaseColor 直连 Emissive，固定曝光，关闭 Bloom。随后逐项查看 R/G/B/A 灰度输出。UV、材质槽或颜色空间出错时，继续堆高光只会掩盖问题。

## 二、漫反射：先建立明暗块面

### 2.1 用平滑分界替代硬 Step

这里使用 sigmoid 控制明暗过渡。`Center` 决定分界位置，`Sharpness` 决定过渡有多窄；LightMap R 提供每个位置自己的偏移。这样，同一个光照角度下，不同区域可以保持不同的亮暗倾向。

<figure class="reference-figure"><img src="/img/pgr-reference/image-1.png" alt="明暗过渡曲线" loading="lazy"><figcaption>明暗过渡曲线</figcaption></figure>

用于 sigmoid 的是带符号的 `N·L`，取值为 −1 到 1。`HalfLambert = N·L × 0.5 + 0.5` 留给后面的 Ramp 采样。把这两个量互换，会导致阈值和整张脸的明暗分布一起偏移。

**材质接法：**`PixelNormalWS` 与归一化的主光方向做 Dot。若高光需要法线纹理，在高光支路单独使用已转换到世界空间的贴图法线；漫反射可先保留较平滑的几何法线，避免细节打碎块面。LightMap R 的编码方式必须随资产确认，示范解码可用 `(R - 0.5) × OffsetScale + GlobalOffset`，其中 0.5 为本文约定的中性值；制作纹理时也要遵循这个约定。

下面是可粘贴进 Custom 的函数体，输出 `CMOT Float1`：

```hlsl
// UE Custom: Output CMOT Float1. All inputs are float1.
// Inputs: NoL, RampOffset, Center, Sharpness, AO, AOStrength, Visibility
// NoL is the SIGNED dot product in [-1,1], not Half Lambert.
float x = NoL + RampOffset;
float exponent = clamp(-max(Sharpness, 0.0) * (x - Center), -80.0, 80.0);
float lit = 1.0 / (1.0 + exp2(exponent));
float ao = lerp(1.0, saturate(AO), saturate(AOStrength));
return lit * ao * saturate(Visibility);
```

这里用 `exp2` 实现 S 型过渡。`Sharpness` 越大，明暗边界越窄；`Center` 移动分界位置。先固定 Center 调整软硬程度，再改变偏移量，便于分辨每个参数对画面的影响。

接线等价于下面的公式；这是合成示意，不是一个包含所有输入声明的独立 Shader：

```hlsl
Dark = BaseColor * ShadowColor * DarkIntensity;
Bright = BaseColor * BrightIntensity;
Diffuse = lerp(Dark, Bright, LitWeight);
```

`AO` 接 LightMap G，`AOStrength` 控制影响程度。`Visibility` 原型先设 1；只有接入实际阴影可见性后，它才代表灯光是否被遮挡。分段后的 Diffuse 不要再无条件乘一次 `saturate(N·L)`，否则亮面会重新变成连续渐变。

### 2.2 面部与身体皮肤分别采样 Ramp

这里用两张 Ramp 为皮肤加入偏暖的过渡色，然后混回 BaseColor，减轻颜色过重的问题。这里是美术颜色近似，不是物理的次表面光输运。

在 UE 中，用 AppendVector 把横坐标与 0.5 合成 UV，分别接到 FaceRamp 与 BodyRamp 的 Texture Sample。下式只用于对应皮肤材质区域：

```hlsl
RampU = saturate(HalfLambert + LightRampAdd + RampOffset * 0.1);
SkinDiffuse = lerp(Diffuse * RampColor, BaseColor, RestoreBase);
```

`RestoreBase` 可以从 0.8 开始调整：值越大，越接近固有色；值越小，Ramp 对明暗颜色的影响越明显。面部使用 FaceRamp，身体裸露皮肤使用 BodyRamp，衣服和头发不走这个分支。按材质区域分别采样，避免同一个像素连续乘两张皮肤 Ramp。

<figure class="reference-figure"><img src="/img/pgr-reference/image-2.png" alt="面部 Ramp 处理前后的对照" loading="lazy"><figcaption>面部 Ramp 处理前后的对照</figcaption></figure>

<figure class="reference-figure"><img src="/img/pgr-reference/image-3.png" alt="身体皮肤 Ramp 处理对照" loading="lazy"><figcaption>身体皮肤 Ramp 处理对照</figcaption></figure>

### 2.3 完整漫反射

此时先不加入镜面反射。观察头发整体亮暗是否清楚、脸部是否保留完整的大色块、衣服底色是否与贴图一致。这一阶段的全身与面部效果如下。

<figure class="reference-figure"><img src="/img/pgr-reference/image-4.png" alt="完整 Diffuse 效果" loading="lazy"><figcaption>完整 Diffuse 效果</figcaption></figure>

<figure class="reference-figure"><img src="/img/pgr-reference/image-5.png" alt=" Diffuse 局部效果" loading="lazy"><figcaption> Diffuse 局部效果</figcaption></figure>

## 三、PBR 高光：把表面反射单独调清楚

### 3.1 从 D、F、G 三项组成 GGX

漫反射决定大色块，镜面项描述光源在表面的集中反射。GGX 的 D 项控制微表面法线分布，F 项描述菲涅耳反射，G 项处理微表面遮挡。粗糙度越小，高光通常越集中；金属度影响基础反射颜色。

<figure class="reference-figure"><img src="/img/pgr-reference/image-6.png" alt=" PBR 高光分解效果" loading="lazy"><figcaption> PBR 高光分解效果</figcaption></figure>

需要压低某个局部的高光时，用单独的区域 Mask 控制。不要把 `(1 - Metallic)` 当作通用高光强度：它会在金属度为 1 时将镜面项归零，使金属区域失去应有的反射。

### 3.2 在 Custom 节点中计算 GGX

输入 `N、L、V、BaseColor` 为 Float3，`Metallic、Roughness` 为 Float1，输出 `CMOT Float3`。N、L、V 必须在同一坐标空间：L 指向灯光，V 指向相机。Normal 贴图解码后用 Tangent → World 的 TransformVector 送入 N。

下面的实现采用 `Roughness = 1 - PBRMask.G`、`alpha = Roughness²`，Schlick 菲涅耳使用 `V·H`。这些是本文 UE 代码的明确约定，不能和不同粗糙度约定的 D 函数混用。

```hlsl
// UE Custom: Output CMOT Float3.
// float3: N, L, V, BaseColor. float1: Metallic, Roughness.
// Output is a BRDF; multiply by light color, NoL and visibility AFTER mixing.
float3 n = normalize(N);
float3 l = normalize(L);
float3 v = normalize(V);
float nl = saturate(dot(n, l));
float nv = saturate(dot(n, v));
float3 sumLV = l + v;
float h2 = dot(sumLV, sumLV);
if (nl <= 0.0 || nv <= 0.0 || h2 < 1e-8) return float3(0, 0, 0);
float3 h = sumLV * rsqrt(h2);
float nh = saturate(dot(n, h));
float vh = saturate(dot(v, h));
float r = clamp(Roughness, 0.08, 1.0);
float alpha = r * r;
float a2 = alpha * alpha;
// Stable form of 1 + (a2-1)*nh*nh; avoids cancellation near nh=1.
float d = (1.0 - nh * nh) + a2 * nh * nh;
float D = a2 / (3.14159265 * d * d);
float gL = 2.0 * nl / (nl + sqrt(a2 + (1.0 - a2) * nl * nl));
float gV = 2.0 * nv / (nv + sqrt(a2 + (1.0 - a2) * nv * nv));
float3 f0 = lerp(float3(0.04, 0.04, 0.04), saturate(BaseColor), saturate(Metallic));
float3 F = f0 + (1.0 - f0) * pow(1.0 - vh, 5.0);
return D * F * gL * gV / max(4.0 * nl * nv, 1e-8);
```

输出只是镜面 BRDF；光色、正向入射余弦和可见性在混合两类高光以后统一相乘。压掉某块手臂的高光，使用独立 `ArtSpecMask` 或 LightMap B，保留 Metallic 的材质含义。粗糙度下限 0.08 是本示例为限制极窄高光而加的约束，可依据抗锯齿条件调整。

<figure class="reference-figure"><img src="/img/pgr-reference/image-7.png" alt="对手臂高光进行美术控制后的效果" loading="lazy"><figcaption>对手臂高光进行美术控制后的效果</figcaption></figure>

## 四、Blinn-Phong 高光：按区域混合两种反射

### 4.1 建立可直接控制的高光形状

Blinn-Phong 用法线 N 与半角向量 H 的点积控制高光，指数越大，亮点越集中。它便于直接调形状，但不等于 GGX，也不会自动生成沿发束延展的各向异性亮带。

<figure class="reference-figure"><img src="/img/pgr-reference/image-8.png" alt=" Blinn-Phong 高光效果" loading="lazy"><figcaption> Blinn-Phong 高光效果</figcaption></figure>

**UE Custom 函数体 · 输出 CMOT Float3：**

```hlsl
// UE Custom: Output CMOT Float3.
// float3: N, L, V, SpecularColor. float1: Exponent.
// Artistic, unnormalized lobe. It is NOT an energy-conserving BRDF.
float3 n = normalize(N);
float3 l = normalize(L);
float3 v = normalize(V);
float3 sumLV = l + v;
float h2 = dot(sumLV, sumLV);
if (dot(n, l) <= 0.0 || dot(n, v) <= 0.0 || h2 < 1e-8)
    return float3(0, 0, 0);
float nh = saturate(dot(n, sumLV * rsqrt(h2)));
return max(SpecularColor, 0.0) * pow(nh, max(Exponent, 1.0));
```

### 4.2 使用 PBRMask A 混合

先单独输出 BP，再单独输出 GGX，最后才接混合。这样可以分辨问题来自算法、通道还是高光许可。

```hlsl
// 节点合成示意；SpecBP / SpecGGX 是两个 Custom 的输出。
Specular = lerp(SpecBP, SpecGGX, saturate(PBRMask.a));
Specular *= saturate(LightMap.b) * saturate(PBRMask.b) * ArtSpecMask;
Specular *= KeyColor * KeyIntensity * saturate(dot(N, L)) * Visibility;
SurfaceColor = Diffuse + Specular;
```

A 为 0 时保留 BP，A 为 1 时选择 GGX；中间值做连续混合。不能把已经乘过主光强度的 GGX 与未乘主光的 BP 放在同一个 Lerp 中，否则切换高光类型会同时改变亮度标尺。

<figure class="reference-figure"><img src="/img/pgr-reference/image-9.png" alt="高光混合过程" loading="lazy"><figcaption>高光混合过程</figcaption></figure>

<figure class="reference-figure"><img src="/img/pgr-reference/image-10.png" alt="混合高光的全身与背部局部" loading="lazy"><figcaption>混合高光的全身与背部局部</figcaption></figure>

## 五、边缘光：比较屏幕邻域的深度

### 5.1 为什么不用一个 Fresnel 就结束

这里采用屏幕深度差提取边缘。对当前角色像素，向周围偏移后采样深度：如果邻居已经落到更远的背景上，就说明当前点靠近可见轮廓。它能够响应屏幕遮挡关系，形状与单纯使用 `1 - N·V` 不同。

<figure class="reference-figure"><img src="/img/pgr-reference/image-11.png" alt="线性深度可视化" loading="lazy"><figcaption>线性深度可视化</figcaption></figure>

<figure class="reference-figure"><img src="/img/pgr-reference/image-17.png" alt="屏幕空间深度差说明" loading="lazy"><figcaption>屏幕空间深度差说明</figcaption></figure>

取中心深度 100 cm、邻居深度 300 cm，邻居减中心为 200 cm，属于可能的轮廓；如果二者都是 100 cm，则没有深度断层。**差分方向应为邻居减中心。**反过来相减会让轮廓判断的方向出错。

在 UE 后处理材质中，先分别取得中心与邻居的线性深度，再将差值转成边缘权重。纹理采样由材质节点完成，阈值和过渡宽度在 Custom 节点中控制。

### 5.2 UE 后处理材质的接线顺序

1. 创建 **Post Process** 材质，读取 `PostProcessInput0` 作为已有画面，最后输出 Emissive。
2. 用 `SceneTexture: SceneDepth` 读取中心和左右上下四个邻居。偏移量为 `WidthPx × InvSize`，InvSize 必须来自所采样的深度纹理。
3. UV 使用该 SceneTexture 对应的坐标，邻居限制在当前视图的有效范围；编辑器视口、动态分辨率下，ViewportUV 不一定等于整张缓冲的 UV。
4. 项目启用带 Stencil 的 Custom Depth，角色主网格写入 CustomDepth 与固定 Stencil 值，例如 7。
5. 结合 Stencil 与 CustomDepth / SceneDepth 的可见性比较，只在可见角色表面合成边缘光。

后处理所在位置会改变曝光空间和时序处理关系，应按项目的 UE 版本检查可用选项。

下面的代码不直接访问纹理，五次采样都由节点完成后作为输入传入。输入要求正的线性视空间深度，单位为 cm；已经线性化的 SceneDepth 不需要再次进行深度解码。可以用相机正前方 300 cm 的平面核对深度值。

```hlsl
// UE Post Process Custom: Output CMOT Float1. All inputs are float1.
// CenterDepth, LeftDepth, RightDepth, UpDepth, DownDepth: linear view depths (cm).
// Threshold, Softness: relative, unitless. VisibleCharacterMask is prepared outside.
float delta = max(max(LeftDepth, RightDepth), max(UpDepth, DownDepth)) - CenterDepth;
float relativeGap = max(delta, 0.0) / max(CenterDepth, 1.0);
float t = max(Threshold, 1e-5);
float s = clamp(Softness, 1e-6, t * 0.99);
float edge = smoothstep(t - s, t + s, relativeGap);
return edge * saturate(VisibleCharacterMask);
```

这里使用相对深度差，让阈值不随距离线性增长，并对四方向取最大值，避免拐角因为累加突然变亮。`WidthPx = 2、Threshold = 0.02、Softness = 0.005` 可作为调试起点，再根据角色尺寸、镜头距离和目标线宽调整。

```hlsl
// 在节点中构造，再传给 DepthRim 的 VisibleCharacterMask。
VisibleCharacterMask = (CustomStencil == 7)
    * (abs(CustomDepth - SceneDepth) < ToleranceCM);
// 在相同曝光空间合成。原型先使用固定 RimColor。
FinalColor = PostProcessInput0 + RimMask * RimColor * RimIntensity;
```

只按 Stencil 判断会让墙后的角色也出现边缘光，因此必须加入深度可见性约束。ToleranceCM 是对浮点误差的容差，应根据项目尺度校准。对于 Unlit 原型，不要假设后处理 GBuffer 中一定保存了可直接取回的角色 BaseColor；若希望边缘光随角色底色变化，需要额外传递角色颜色。

先采用固定像素宽度便于校准；如果希望距离越远边缘越细，可以把宽度乘 `ReferenceDepth / max(CenterDepth, 1)` 并做上下限约束。透视投影中的 clip W 与视空间深度相关，不等同于相机到像素的欧氏距离。

<figure class="reference-figure"><img src="/img/pgr-reference/5abf09d20a66c465e3c0dddc7830a3a22c2d0829.gif" alt="深度边缘光动态演示" loading="lazy"><figcaption>深度边缘光动态演示</figcaption></figure>

<figure class="reference-figure"><img src="/img/pgr-reference/image-19.png" alt="将边缘光与角色颜色合成后的效果" loading="lazy"><figcaption>将边缘光与角色颜色合成后的效果</figcaption></figure>

## 六、描边：外扩背面与顶点色控制

### 6.1 先观察脸部的描边分布

这里使用反向外壳描边：复制轮廓几何、沿法线外扩、剔除正面，露出的背面形成轮廓线。顶点色 A 调宽度，B 调深度方向偏移，让鼻子、眼周和头发不必统一使用一条粗黑线。

<figure class="reference-figure"><img src="/img/pgr-reference/image-20.png" alt="面部顶点色与描边控制" loading="lazy"><figcaption>面部顶点色与描边控制</figcaption></figure>

<figure class="reference-figure"><img src="/img/pgr-reference/image-21.png" alt="描边局部结果" loading="lazy"><figcaption>描边局部结果</figcaption></figure>

实现时把轮廓拆成独立网格，通过 World Position Offset 控制外扩，利用面朝向遮罩保留背面。宽度和深度偏移分别由顶点色 A、B 调节，线色则由 BaseColor 推导。

### 6.2 创建轮廓网格与 WPO 材质

给角色增加一个 OutlineMesh 组件，用独立材质绘制外壳：静态角色使用相同网格与变换；骨骼角色使用兼容的骨骼网格，并通过 Leader Pose 跟随主体姿态。轮廓组件关闭阴影投射、碰撞和 CustomDepth 写入。

轮廓材质设为 **Surface / Masked / Unlit / Two Sided**。用下式保留背面，遮掉不需要的面：

```hlsl
OpacityMask = saturate(-TwoSidedSign)
    * step(0.0001, VertexColor.a);
```

Opacity Mask Clip Value 设为 0.5。A 为 0 时不仅停止外扩，还要移除壳面，否则共面区域仍可能出现黑块。实际网格的面朝向、导入缩放也必须正确。

把下面 Custom 的 Float3 输出接 **World Position Offset**：

```hlsl
// UE Custom: Output CMOT Float3, connect ONLY to World Position Offset.
// float3: VertexNormalWS, CameraRightWS, CameraUpWS, CameraForwardWS.
// float1: WidthCM, VertexAlpha, VertexBlue, DepthBias.
// Camera axes must be an orthonormal camera frame, Forward points into the scene.
float3 n = normalize(VertexNormalWS);
float nx = dot(n, CameraRightWS);
float ny = dot(n, CameraUpWS);
float nz = DepthBias * (1.0 - saturate(VertexBlue));
float3 direction = CameraRightWS * nx + CameraUpWS * ny + CameraForwardWS * nz;
return direction * max(WidthCM, 0.0) * saturate(VertexAlpha);
```

`VertexNormalWS` 接顶点法线；A/B 接顶点色。相机 Right / Up / Forward 使用归一化世界基底，Forward 指向场景，在单相机原型中可每帧写入参数集合。该共享参数方案不适用于同时渲染不同相机视图的分屏或立体场景。

`WidthCM` 以厘米为单位，可从 0.1～0.2 cm 试起；`DepthBias` 初始设 0。导入缩放会影响实际线宽，应按 UE 场景中的角色尺寸重新标定。外扩后还要检查 Bounds、LOD 和动画变形，避免轮廓提前被裁掉。

### 6.3 从底色推导线色

描边可以根据材质底色变化。下面写成 UE Custom 函数体；输入 `BaseColor、OutlineColor` 为 Float3，输出 Float3 后接 Emissive：

```hlsl
float peak = max(max(BaseColor.r, BaseColor.g), BaseColor.b) - 0.004;
float3 vivid = step(float3(peak, peak, peak), BaseColor) * BaseColor;
vivid = lerp(BaseColor, vivid, 0.6);
return 0.5 * vivid * BaseColor * OutlineColor;
```

深红衣服会得到偏红的暗线，头发则保留接近自身颜色的轮廓。先调出稳定的宽度，再调线色；过亮的线色与深度边缘光叠加后，容易把轮廓变成双层亮边。

## 七、最后效果：把各层放回同一画面

完成上述步骤后再加入后处理。结合下面的多视角效果，逐项辨认漫反射、高光和轮廓对整体质感的贡献，再回到各个分支调整参数。

<figure class="reference-figure"><img src="/img/pgr-reference/image-22.png" alt="进入最终后处理阶段的多视角展示" loading="lazy"><figcaption>进入最终后处理阶段的多视角展示</figcaption></figure>

<figure class="reference-figure"><img src="/img/pgr-reference/image-24.png" alt="最终效果：侧面与背景后处理" loading="lazy"><figcaption>最终效果：侧面与背景后处理</figcaption></figure>

<figure class="reference-figure"><img src="/img/pgr-reference/image-23.png" alt="最终效果：正面与面部" loading="lazy"><figcaption>最终效果：正面与面部</figcaption></figure>

在 UE 中先固定曝光，把 BaseColor、Diffuse、Specular、RimMask、Outline 分别保存，再叠加 Bloom 与调色。不要靠强 Bloom 掩盖贴图不匹配、亮面过曝或脸部形状错误。转动主光、转动角色、拉远镜头，分别观察高光移动、面部阴影与远景线宽；这些动态变化是判断材质是否成立的一部分。

| 阶段 | 保留的输出 | 核对重点 |
| --- | --- | --- |
| 贴图 | BaseColor 与单通道灰度 | UV、材质区域、数值与颜色空间 |
| 漫反射 | Diffuse | 分界位置、软硬过渡、皮肤 Ramp |
| 高光 | BP / GGX / 混合结果 | 粗糙度、PBR 倾向、区域屏蔽 |
| 边缘光 | 线性深度、可见角色 Mask、RimMask | 采样方向、像素宽度、遮挡 |
| 描边 | 外壳与顶点色 A/B | 面部黑块、裂缝、动画同步 |
| 后处理 | 固定曝光下的完整画面 | 肤色、暗部层次、高光稳定性 |

## 配套代码

[下载 UE 材质代码](/downloads/character-lab/ue-toon-kit.zip) · [阅读接线说明](/downloads/character-lab/README.md)

代码包包含五个 Custom 节点函数体、CPU 数学实现与检查脚本。按接线说明在 UE 中建立材质节点即可开始调试。包内不含 `.uproject`、模型或完整纹理；代码已完成 CPU 数学检查，尚未进行 UE 内编译与画面对照。

<small>配图来源：挽秋[《战双卡通渲染复现》](https://xiatianlaila.github.io/2023/10/14/战双卡通渲染复现/)，按 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) 使用；配图用于效果讲解，不是本文 UE 代码的运行截图。通道总览右下角已替换为 AI 生成的 Body SSS Ramp 示意。角色与资产权利归相应权利人。</small>

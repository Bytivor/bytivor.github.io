---
title: 实时渲染抗锯齿：从 MSAA、TAA 到 UE 中的画质取舍
date: 2022-08-20 17:15:00
permalink: 2026/09/10/anti-aliasing-msaa-taa/
demo_views: 168
demo_likes: 9
updated: 2026-09-10 17:18:55
categories: 渲染原理
tags: [Unreal Engine, 抗锯齿, MSAA, TAA, SMAA, FXAA, HLSL]
cover: /img/anti-aliasing/cover.svg
description: 从一个像素的覆盖率讲起，逐步拆解 MSAA、TAA、MLAA、SMAA 与 FXAA，结合图解、公式和代码，理解移动端带宽、UE 设置及性能对照。
toc: true
---

在角色材质和场景光照调到比较满意之后，画面往往还差最后一点稳定感：武器斜边上能看到台阶，远处的发丝时隐时现，金属高光随着镜头移动不断闪烁。打开抗锯齿后，轮廓可能平滑了，细节却变软；换一种算法，静态截图更清楚，运动时又出现拖影。

这些现象看起来都属于“锯齿”，但发生的位置并不相同。有的是几何边缘只覆盖了一小部分像素，有的是材质内部变化太快，还有的是当前帧与历史帧没有正确对应。想把抗锯齿用好，需要先弄清楚：**算法获得了什么额外信息，又在哪里把这些信息合成回一个像素。**

这篇文章从 SSAA 和 MSAA 的空间采样开始，再拆解 TAA 的时间积累，以及 MLAA、SMAA、FXAA 对最终图像的处理方式。最后回到 UE，讨论设置、移动端带宽与性能验证，让选型建立在实际画面问题上。

<div class="face-lead"><div><b>SPACE</b><strong>空间里增加样本</strong><p>理解覆盖率、逐样本深度与 Resolve。</p></div><div><b>TIME</b><strong>时间里积累信息</strong><p>理解抖动、重投影与历史修正。</p></div><div><b>IMAGE</b><strong>图像里重建边缘</strong><p>理解边缘搜索、面积权重与混合。</p></div></div>

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image7.png" width="784" height="746" alt="同一类几何边缘在关闭 MSAA、2×、4×、8× MSAA 下的局部对照。" loading="lazy"><figcaption><span>图 01</span> 同一类几何边缘在关闭 MSAA、2×、4×、8× MSAA 下的局部对照。</figcaption></figure>

<!-- more -->

## 01 / 从一个像素开始：为什么会出现台阶

一个像素代表一小块屏幕区域，而最简单的光栅化只在其中一个位置判断三角形是否覆盖。如果一条斜边擦过像素，中心点恰好在三角形外，整块像素就可能被记为背景；移动一点点，中心点进入三角形，又会变成完整的前景色。

理想情况下，我们希望像素颜色能反映这块区域中不同表面所占的比例。用有限数量的采样点估计覆盖情况，就是空间抗锯齿的起点。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image1.png" width="744" height="201" alt="单点采样可能漏掉局部覆盖；增加子像素样本后，可以估计前景与背景的混合比例。" loading="lazy"><figcaption><span>图 02</span> 单点采样可能漏掉局部覆盖；增加子像素样本后，可以估计前景与背景的混合比例。</figcaption></figure>

### SSAA：覆盖、深度和着色一起增加

SSAA（Super Sampling Anti-Aliasing，超级采样抗锯齿）在一个输出像素范围内取得多个完整着色样本，再通过重建滤波得到最终颜色。它既能改善几何边缘，也能帮助处理材质和光照产生的高频变化，但通常需要更多着色与存储开销。

例如将宽、高都提高到两倍再降采样，像素总量会变成四倍。这里的“4×”指样本总量，不是宽和高各提高四倍。纹理 LOD、样本位置和重建滤波器也会影响最终效果，不能只看倍数。

### MSAA：把覆盖采样频率与着色频率拆开

MSAA（Multi-Sample Anti-Aliasing，多重采样抗锯齿）同样在一个像素中放置多个样本，分别判断覆盖和深度；在常见的像素频率着色模式下，同一个图元可以共享一次像素着色结果，将颜色写入通过测试的样本。

**“一个像素只着色一次”需要加上条件。** 多个图元覆盖同一像素时，仍可能各自触发着色；逐样本着色、辅助着色线程、透明叠加等也会改变执行次数。MSAA 节省的是通常无需对每个覆盖样本重复完整材质计算，而不是保证整帧每个像素都只执行一次 Shader。

## 02 / 4× MSAA：逐步跟踪一个像素

### 三个三角形进入同一个像素

下面用 A、B、C 三个三角形展示覆盖关系。灰色方框表示一个像素，四个黑点是子像素样本，红点表示着色位置示意。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image2.png" width="381" height="357" alt="一个像素内的四个样本，以及依次绘制的三个三角形 A、B、C。" loading="lazy"><figcaption><span>图 03</span> 一个像素内的四个样本，以及依次绘制的三个三角形 A、B、C。</figcaption></figure>

为避免掩码的书写顺序混淆，本文规定样本 1 对应最低位，样本 4 对应最高位。如果 A 覆盖样本 3、4，按 bit 3 到 bit 0 写出的掩码就是 `1100`。关键是每一位对应哪个样本，而不是把图中的上下排列当成二进制顺序。

### 覆盖测试决定哪些样本有资格写入

光栅化首先确定三角形覆盖了哪些样本。对没有被覆盖的位置，这个图元不会更新颜色。覆盖结果随后与深度、模板等测试共同决定写入资格。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image3.png" width="122" height="122" alt="A 的覆盖示意：下方两个样本被覆盖。小图的方格表示样本槽位，不是新增的屏幕像素。" loading="lazy"><figcaption><span>图 04</span> A 的覆盖示意：下方两个样本被覆盖。小图的方格表示样本槽位，不是新增的屏幕像素。</figcaption></figure>

### 每个样本保留自己的遮挡关系

A 通过测试后，下方两个样本存入 A 的深度和颜色。接着绘制 B、C；若它们覆盖同一个样本，并且 C 在该处更靠近相机，C 会替换 B。其他样本的颜色不受影响。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image6.png" width="361" height="313" alt="逐样本保存可见表面：B 与 C 的竞争只改变它们共同覆盖的样本，不会覆盖整个像素。" loading="lazy"><figcaption><span>图 05</span> 逐样本保存可见表面：B 与 C 的竞争只改变它们共同覆盖的样本，不会覆盖整个像素。</figcaption></figure>

| 样本 | A 绘制后 | B 绘制后 | C 绘制后 |
| --- | --- | --- | --- |
| 1 | 背景 | 背景 | 背景 |
| 2 | 背景 | B | C（深度测试通过） |
| 3 | A | A | A |
| 4 | A | A | A |

表格只描述这个示意案例。硬件可通过 Early-Z 等机制重排或提前执行测试，不能把这段说明理解成所有 GPU 固定的执行时序。

### Resolve：把四个颜色还原为一个

采用等权颜色 Resolve 时，最终像素是四个样本的平均值：

<div class="face-equation"><code>Cout = (C₁ + C₂ + C₃ + C₄) / 4</code><code>Cout = (Cbg + C_C + 2 × C_A) / 4</code><span>C_A 与 C_C 分别表示三角形 A、C 的颜色，Cbg 表示背景。所有颜色应在约定一致的空间中计算。</span></div>

下面的 HLSL 仅演示一个四样本颜色纹理的等权读取，输出到普通单样本渲染目标。它是图形接口层的示例，不是可以直接粘进 UE 普通材质 Custom 节点的完整功能。

```hlsl
Texture2DMS<float4, 4> SourceMS : register(t0);

float4 ResolvePS(float4 position : SV_Position) : SV_Target0
{
    int2 pixel = int2(position.xy);
    float4 sum = 0.0;
    [unroll]
    for (int sampleIndex = 0; sampleIndex < 4; ++sampleIndex)
        sum += SourceMS.Load(pixel, sampleIndex);
    return sum * 0.25;
}
```

深度不能直接照搬这个平均操作。一个像素中同时存在前景与背景深度时，平均值可能落在一个根本不存在的表面上；后续效果需要最近深度、最远深度还是其他表示，应由用途和图形接口能力决定。

### Centroid 插值需要显式约定

像素中心未被三角形覆盖时，中心插值可能落到图元外侧。`centroid` 插值可以让相关属性在像素被覆盖的区域内求值，减少边缘属性外插问题；它不是开启 MSAA 后自动启用的“总是选择最近样本”规则，也不能与逐样本着色混为一谈。具体规则可核对 [Direct3D 光栅化说明](https://learn.microsoft.com/en-us/windows/win32/direct3d11/d3d10-graphics-programming-guide-rasterizer-stage-rules)。

## 03 / MSAA 擅长什么，成本又在哪里

MSAA 最直接的收益来自几何覆盖边缘。一根真实几何细线，即使没有覆盖像素中心，也可能覆盖某个子样本；单帧后处理拿不到这个被单点采样漏掉的几何信息。

但如果闪烁来自三角形内部的尖锐高光、法线纹理或硬阈值，而材质仍按像素频率着色，增加覆盖样本并不会自动增加这些信号的着色样本。纹理过滤、材质抗锯齿、适当的粗糙度与时间积累仍然有各自的作用。

这也解释了为什么[面部阴影中的 fwidth 优化](/2026/09/10/face-shadow-antialiasing/)仍有意义：面部 SDF 生成的明暗分界位于三角形内部，仅打开 MSAA，通常无法解决硬 `step` 带来的全部锯齿。

### 样本数增加的是存储维度

对于一个未压缩、普通存储的 W×H 渲染目标，若每个颜色样本占 B 字节，S 个样本的逻辑颜色容量约为 `W × H × S × B`。深度与模板附件还要单独计算。

例如 1920×1080、RGBA16F（每样本 8 字节）、4× MSAA，逻辑多样本颜色数据约为 **63.3 MiB**；一个单样本颜色目标约为 **15.8 MiB**。这不是整帧总显存，也没有计入压缩、片上驻留、对齐与其他附件。

4× MSAA 的图像仍是 W×H，只是每个像素多了样本维度。它与 2W×2H 超采样的逻辑样本数量相同，布局和着色行为却不同。

## 04 / TAA：把额外样本放进时间

TAA（Temporal Anti-Aliasing，时间抗锯齿）通过逐帧改变采样位置，将历史信息重投影到当前画面，再经过有效性判断与颜色修正进行积累。它不需要在同一帧中完成所有子像素采样，但需要判断历史结果还能不能用。

<div class="face-flow"><span>抖动采样</span><i>→</i><span>当前帧</span><i>＋</i><span>历史重投影</span><i>→</i><span>有效性与颜色修正</span><i>→</i><span>混合并保存历史</span></div>

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image8.png" width="1148" height="800" alt="TAA 的跨帧数据流：当前帧不断提供新样本，历史结果在校验后参与重建。" loading="lazy"><figcaption><span>图 06</span> TAA 的跨帧数据流：当前帧不断提供新样本，历史结果在校验后参与重建。</figcaption></figure>

### 抖动相机投影，改变采样位置

抖动不是让相机在场景中明显摇晃，而是在投影中引入很小的子像素偏移。同一条边缘在连续帧中被不同位置采到，历史积累才有机会获得更丰富的覆盖信息。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image9.png" width="755" height="204" alt="投影抖动改变光栅化网格与几何的相对位置，让连续帧获得不同的子像素信息。" loading="lazy"><figcaption><span>图 07</span> 投影抖动改变光栅化网格与几何的相对位置，让连续帧获得不同的子像素信息。</figcaption></figure>

Halton 序列是常见选择之一，但不是所有 TAA 必须使用的序列。序列长度、循环方式与采样分布都要配合重建滤波设计。

约定 JitterPx 以渲染像素为单位、NDC 的宽高范围各为 2，则可以写成：

```hlsl
// 示意：NDC 的 Y 正方向与屏幕 Y 方向必须在接入时统一。
float2 jitterNDC = 2.0 * JitterPx / RenderSize;
ClipPosition.xy += jitterNDC * ClipPosition.w;
```

比起死记投影矩阵的某两个下标，更可靠的是明确行/列向量约定和透视除法：乘上 `w` 后，除法得到的是期望的 NDC 平移。抖动符号也应与引擎的屏幕坐标系一致。

### 重投影：找到同一个表面上一帧的位置

对于静止几何，可以把当前深度对应的位置恢复到世界空间，再投影到上一帧。这里采用列向量记法：

<div class="face-equation"><code>WorldH = inverse(CurrentVP) × CurrentClip</code><code>World = WorldH.xyz / WorldH.w</code><code>PreviousClip = PreviousVP × float4(World, 1)</code><span>再经过透视除法与屏幕映射，得到 PreviousUV。深度范围和抖动约定必须一致。</span></div>

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image14.png" width="753" height="320" alt="相机发生变化时，通过当前与历史变换找到同一世界位置对应的屏幕坐标。" loading="lazy"><figcaption><span>图 08</span> 相机发生变化时，通过当前与历史变换找到同一世界位置对应的屏幕坐标。</figcaption></figure>

运动物体还需要上一帧的对象变换；骨骼、布料和顶点动画则需要对应的历史变形信息。只用相机矩阵无法恢复这些运动。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image15.png" width="725" height="197" alt="运动矢量表达同一个表面从上一帧到当前帧的屏幕位移。" loading="lazy"><figcaption><span>图 09</span> 运动矢量表达同一个表面从上一帧到当前帧的屏幕位移。</figcaption></figure>

如果约定 `VelocityUV = CurrentUV − PreviousUV`，那么 `PreviousUV = CurrentUV − VelocityUV`。有些实现用像素单位、不同正负号或编码后的速度纹理，因此不能把任意 Velocity Buffer 直接代入这一公式。

### 重投影位置存在，不代表历史有效

被前景遮挡的背景突然露出时，上一帧没有当前背景的可靠颜色；镜头切换、深度突变和不正确的运动矢量，也会让历史采样失效。此时应丢弃历史或大幅降低其权重。

在邻域中选取前景速度可以帮助某些轮廓位置找到更合适的运动信息，但它无法凭空恢复被遮挡的背景。颜色校正也只是第二道限制，不能替代几何有效性判断。TAA 的工程重点正是这些历史管理问题，相关流程可结合 [Epic 的时序超采样讲解](https://www.advances.realtimerendering.com/s2014/index.html#_HIGH-QUALITY_TEMPORAL_SUPERSAMPLING)理解。

## 05 / 历史修正与混合：稳定和拖影之间的取舍

### 用当前邻域约束历史颜色

简单方法是在当前像素的 3×3 邻域中求颜色最小值和最大值，形成颜色空间中的 AABB。历史颜色落在范围外时，将它限制到合理区域。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image17.png" width="413" height="309" alt="邻域颜色形成的包围盒。可以在 RGB 或适当的亮度—色度空间内构造边界。" loading="lazy"><figcaption><span>图 10</span> 邻域颜色形成的包围盒。可以在 RGB 或适当的亮度—色度空间内构造边界。</figcaption></figure>

`clamp` 对每个通道分别截断，成本直接，但可能把颜色推向盒子的角；`clip` 沿选定方向与盒子求交，更好地保持该方向上的颜色关系。下图展示了两种处理方式的区别。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image18.png" width="464" height="368" alt="Clamped Color 与 Clipped Color 的二维示意：逐通道截断与沿方向裁剪会得到不同结果。" loading="lazy"><figcaption><span>图 11</span> Clamped Color 与 Clipped Color 的二维示意：逐通道截断与沿方向裁剪会得到不同结果。</figcaption></figure>

下面演示从 AABB 中心指向历史颜色的裁剪。它要求输入处于同一颜色空间，Lo/Hi 已由当前邻域求得。

```hlsl
float3 ClipHistoryToBox(float3 history, float3 lo, float3 hi)
{
    float3 center = 0.5 * (lo + hi);
    float3 extent = max(0.5 * (hi - lo), 1e-5);
    float3 offset = history - center;
    float3 normalized = abs(offset) / extent;
    float scale = max(1.0, max(normalized.x,
                             max(normalized.y, normalized.z)));
    return center + offset / scale;
}
```

这只是历史颜色限制函数，不是一套完整 TAA。还需要历史纹理、重投影、边界判断、深度有效性、曝光匹配与重置策略。放宽颜色范围容易保留错误历史；收得过紧则会损失积累效果，重新出现闪烁。

### 保存上一帧的积累结果，就能递归保留更早的信息

令 Cₜ 为当前颜色，Hₜ 为积累结果，α 为**当前帧权重**：

<div class="face-equation"><code>Hₜ = αCₜ + (1 − α)Hₜ₋₁</code><code>wₖ = α(1 − α)ᵏ</code><span>第 k 帧之前的颜色贡献呈指数衰减，并不是线性减少。</span></div>

它与 N 帧等权平均不完全相同，也不需要保留 N 张完整历史图。`α = 0.1` 时，旧历史每经过一帧就乘 0.9；降低 α 可以延长积累，但也会减慢对画面变化的响应。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/history-decay.svg" alt="历史权重的解析曲线：当前帧权重越小，旧信息保留得越久。图中是数学示意，不是 GPU 测试。" loading="lazy"><figcaption><span>图 12</span> 历史权重的解析曲线：当前帧权重越小，旧信息保留得越久。图中是数学示意，不是 GPU 测试。</figcaption></figure>

```hlsl
// validHistory 由 UV、深度、镜头切换等检查共同决定。
float currentWeight = validHistory ? saturate(alpha) : 1.0;
float3 result = lerp(correctedHistory, currentColor, currentWeight);
```

静态、正确对应的画面中，TAA 可以持续积累信息；运动、遮挡与光照变化会不断打断积累。因此不能保证它在任何场景里都“等同于 4× SSAA”。

## 06 / MLAA：从已经画好的图像重建边缘

单帧图像抗锯齿拿到的是渲染后的颜色，不直接拥有三角形的真实覆盖信息。MLAA（Morphological Anti-Aliasing，形态抗锯齿）的思路是识别阶梯形边界，估计连续边缘穿过像素的方式，再用覆盖面积近似计算混合权重。

<div class="face-flow"><span>边缘检测</span><i>→</i><span>沿边缘搜索</span><i>→</i><span>估计面积权重</span><i>→</i><span>邻域颜色混合</span></div>

### 第一遍：把边界存成可查询的数据

通过亮度、颜色差异，或可用的深度信息判断相邻像素之间是否存在边缘。由于相邻像素共享边界，只保存两个方向即可避免重复；本例用 R 保存左边界，用 G 保存上边界。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image23.png" width="682" height="202" alt="将左边界与上边界分别写入 R/G 通道，得到边缘纹理。" loading="lazy"><figcaption><span>图 13</span> 将左边界与上边界分别写入 R/G 通道，得到边缘纹理。</figcaption></figure>

单纯超过对比度阈值，并不能证明这里存在几何轮廓。纹理细节也会被检出，所以阈值设计会影响细节保留与误判。

### 第二遍：搜索长度和端点形状

沿边缘两侧搜索，可以得到这段边缘的长度以及端点交叉方向。利用这些信息，近似重建一条连续线，估计线穿过像素的面积。

双线性过滤在这里用于解码边缘数据：两个二值样本等权混合会产生 0、0.5、1；改变采样位置，可以让两端信息以不同权重进入结果，从而减少某些形状歧义。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image26.png" width="1204" height="298" alt="改变采样偏移后，0、0.25、0.75、1 可以区分不同的二值边缘组合。具体取值依赖图中的采样位置。" loading="lazy"><figcaption><span>图 14</span> 改变采样偏移后，0、0.25、0.75、1 可以区分不同的二值边缘组合。具体取值依赖图中的采样位置。</figcaption></figure>

边缘纹理是数值数据，需要保持通道和过滤约定；sRGB 解码、错误 Mip 或不匹配的采样偏移会破坏这些编码。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image27.png" width="535" height="448" alt="根据重建边缘的走向，估计对侧颜色应混入当前像素的面积比例 a。" loading="lazy"><figcaption><span>图 15</span> 根据重建边缘的走向，估计对侧颜色应混入当前像素的面积比例 a。</figcaption></figure>

将常见端点与长度组合预计算为面积查询表，可以减少运行时计算。RGBA 混合权重的方向约定由实现决定，生成和读取必须配套，不宜把某个实现的通道顺序当作通用规则。

### 第三遍：按权重进行邻域混合

最简单的单边混合为 `Cnew = (1 − a) × Cold + a × Copp`，a 表示对侧颜色的贡献。多个方向同时参与时，按设计的权重组合，避免直接叠加使颜色能量异常。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image32.png" width="644" height="550" alt="阶梯边缘经过面积权重混合后，形成连续斜线的视觉近似。" loading="lazy"><figcaption><span>图 16</span> 阶梯边缘经过面积权重混合后，形成连续斜线的视觉近似。</figcaption></figure>

它重建的是图像中已经留下的边缘证据。完全没被采到的细线、单帧中消失的发丝，无法依靠邻域混合可靠恢复。

## 07 / SMAA：让边缘判断更谨慎

SMAA 在形态抗锯齿的基础上改进局部对比度判断、斜线搜索、拐角保留和面积估计。这里主要讨论单帧的 SMAA 1×；带空间或时间采样的其他模式不能简单归为同一种单帧后处理。算法模式与配套查询表可查看 [SMAA 项目说明](https://www.iryoku.com/smaa/)。

### 用局部对比度抑制弱边缘误判

在初次检测到边缘后，再比较附近更强的亮度差。如果候选边缘相对邻域变化太弱，就可以抑制它。比较的是**相邻像素的对比度**，不是某个像素的绝对亮度。

设候选差值为 Δ，邻域最大差值为 Δmax，示意判定可以写成 `Δ ≥ Threshold` 且 `AdaptFactor × Δ ≥ Δmax`。实际采样位置与系数应和实现版本保持一致。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image33.png" width="162" height="162" alt="局部邻域参与对比度判断，减少较弱纹理变化被当成主要轮廓的情况。" loading="lazy"><figcaption><span>图 17</span> 局部邻域参与对比度判断，减少较弱纹理变化被当成主要轮廓的情况。</figcaption></figure>

### 保留尖角，单独处理斜线

如果所有边缘都按长直线重建，尖角会被磨圆，连续斜线也可能出现不均匀的混合。SMAA 增加对角方向的搜索，并识别交叉边缘与拐角结构。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image34.png" width="535" height="228" alt="拐角附近需要单独判断，避免边缘平滑抹掉原本清楚的几何转折。" loading="lazy"><figcaption><span>图 18</span> 拐角附近需要单独判断，避免边缘平滑抹掉原本清楚的几何转折。</figcaption></figure>

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image35.png" width="583" height="188" alt="斜线搜索帮助识别连续的对角轮廓，使面积权重不只依赖水平和垂直模式。" loading="lazy"><figcaption><span>图 19</span> 斜线搜索帮助识别连续的对角轮廓，使面积权重不只依赖水平和垂直模式。</figcaption></figure>

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image37.png" width="711" height="366" alt="对角线两端的交叉模式与预计算面积表。查询表编码必须与搜索逻辑一致。" loading="lazy"><figcaption><span>图 20</span> 对角线两端的交叉模式与预计算面积表。查询表编码必须与搜索逻辑一致。</figcaption></figure>

### 双线性过滤也可以压缩边缘查询

在特定的 2×2 二值布局下，选择不对称的采样位置，可以把四个值编码进一个过滤结果。以下图的 C1 左下、C2 左上、C3 右下、C4 右上为例，采样位置偏向左下时，可得到：

<div class="face-equation"><code>v = (10C1 + 5C2 + 2C3 + C4) / 18</code><span>四个输入分别为 0 或 1，这组权重可区分 16 种组合；它是特定布局下的编码示意。</span></div>

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image41.png" width="445" height="396" alt="2×2 二值样本的加权读取。权重取决于相对于四个纹素中心的实际位置。" loading="lazy"><figcaption><span>图 21</span> 2×2 二值样本的加权读取。权重取决于相对于四个纹素中心的实际位置。</figcaption></figure>

这类优化必须与查询表精确匹配，不能把示意偏移直接套到任意边缘纹理。运行时搜索仍有上限，纹理精度和过滤约定也必须满足解码要求。

## 08 / FXAA：在单个 Pass 中完成图像平滑

FXAA（Fast Approximate Anti-Aliasing，快速近似抗锯齿）从最终颜色的局部对比度入手，在一个全屏 Pass 中完成判断和过滤。以下按 Quality 路径的思路讲解；不同预设的搜索步数、阈值和实现细节会有所不同。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image42.png" width="353" height="325" alt="用 M 表示中心，N/S/E/W 表示四邻域，先估计局部对比度。" loading="lazy"><figcaption><span>图 22</span> 用 M 表示中心，N/S/E/W 表示四邻域，先估计局部对比度。</figcaption></figure>

### 低对比度区域尽早退出

先比较中心与四邻域的亮度范围。范围很小时，直接保留原色，可以避免在平坦区域做更多边缘搜索。

```hlsl
// 输入是按同一约定得到的五个亮度值；这里只演示早退条件。
float lumaMin = min(M, min(min(N, S), min(E, W)));
float lumaMax = max(M, max(max(N, S), max(E, W)));
float range = lumaMax - lumaMin;
bool needsAA = range >= max(AbsoluteThreshold,
                           RelativeThreshold * lumaMax);
```

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image43.png" width="704" height="220" alt="左侧亮度范围较大，需要继续判断；右侧差异较小，可以提前结束。" loading="lazy"><figcaption><span>图 23</span> 左侧亮度范围较大，需要继续判断；右侧差异较小，可以提前结束。</figcaption></figure>

### 方向判断、端点搜索与子像素过滤

通过包括对角位置在内的邻域亮度变化，估计边缘更接近水平还是垂直；接着沿边缘方向寻找端点，决定沿垂直于边缘的方向偏移多少。子像素过滤项则处理局部亮度与邻域均值的偏差，两类信息共同影响最后的取样位置。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image47.png" width="214" height="213" alt="邻域加权示意。方向估计与子像素过滤依赖局部亮度结构，而不是简单平均整张画面。" loading="lazy"><figcaption><span>图 24</span> 邻域加权示意。方向估计与子像素过滤依赖局部亮度结构，而不是简单平均整张画面。</figcaption></figure>

单 Pass 减少了中间目标和阶段切换，但不意味着只有一次纹理采样。高对比度区域仍可能触发多个邻域读取和搜索；具体成本取决于预设与画面内容。可结合 [NVIDIA 的 FXAA 说明](https://developer.download.nvidia.com/assets/gamedev/files/sdk/11/FXAA_WhitePaper.pdf)理解其局部过滤思路。

FXAA 不依赖历史帧，因此不会产生错误历史累积造成的拖影；代价是没有真实的跨帧子像素信息，过滤过强时，纹理、细线与文字可能变软。UI 是否进入这个 Pass，也会影响最终清晰度。

## 09 / 移动端：On-chip MSAA 与 Alpha-to-Coverage

### 片上 Resolve 为什么重要

分块渲染架构把屏幕划分为若干 tile，在处理一个 tile 时尽量将颜色、深度等数据留在片上。若多样本结果能在写回外部内存前完成 Resolve，就有机会避免把完整的多样本附件先写出、再读回。

不能把所有移动 GPU 的 tile 都写成固定 16×16，也不能把所有桌面 GPU 简化成完全没有分块机制。这里应关注的是**数据能否留在片上，以及什么时候必须存储到外部内存**。

Transient、Memoryless 或合适的 Store Action 可以帮助表达“不需要保存多样本中间结果”。但片上容量、样本测试与 Resolve 仍然有成本；跨 Pass 读取深度还可能改变附件生命周期。相关取舍可对照 [Khronos 的 MSAA 性能示例](https://docs.vulkan.org/samples/latest/samples/performance/msaa/README.html)。

### 深度读取是管线设计问题

水体、贴花和屏幕空间效果需要场景深度时，要确认该深度在哪个阶段可读，是否已经被丢弃，以及保存的是设备深度还是线性视空间深度。Device Z 通常需要通过投影关系解码，不能直接称为厘米单位的线性深度。

Framebuffer Fetch、Input Attachment、显式深度存储与深度 Resolve 都有各自的接口和设备条件。把某个版本的移动端实现概括为“ES 3.1 必然支持”，会掩盖真正的兼容性要求。

### Alpha-to-Coverage：把 Alpha 转成样本掩码

树叶和毛发卡片的轮廓往往来自纹理 Alpha，而不是三角形边界。普通 Alpha Test 直接通过或丢弃，边缘容易出现硬台阶。Alpha-to-Coverage（A2C）将 Alpha 转成多样本覆盖掩码，再与几何覆盖掩码结合。

<div class="face-equation"><code>FinalMask = GeometryMask AND AlphaMask</code><span>之后仍要满足其他样本测试。A2C 不是普通透明混合，也不是固定的逐样本随机投硬币。</span></div>

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image44.webp" width="720" height="175" alt="从左到右：Alpha Test、Alpha Blend、Alpha-to-Coverage，以及结合锐化的 A2C 效果。" loading="lazy"><figcaption><span>图 25</span> 从左到右：Alpha Test、Alpha Blend、Alpha-to-Coverage，以及结合锐化的 A2C 效果。</figcaption></figure>

在 4× MSAA 下，Alpha 为 0.5 可以形成约一半样本的覆盖模式，但与局部几何掩码相交后，不保证任意像素都恰好保留一半已覆盖样本。具体 Alpha 到掩码的映射由实现决定；其语义可核对 [Direct3D 的 A2C 说明](https://learn.microsoft.com/en-us/windows/win32/direct3d11/d3d10-graphics-programming-guide-blend-state#alpha-to-coverage)。

## 10 / 放回 UE：区分算法、渲染路径与版本

下面的桌面设置以 **UE 5.6** 为范围；界面配图保留 UE4 阶段的设置示意。移动端、其他版本和项目覆盖配置要分别检查，不能把旧菜单或旧命令当作所有版本的统一入口。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image50.png" width="1258" height="680" alt="UE4 的抗锯齿方法设置界面示意。UE5 的选项与平台划分应以实际版本为准。" loading="lazy"><figcaption><span>图 26</span> UE4 的抗锯齿方法设置界面示意。UE5 的选项与平台划分应以实际版本为准。</figcaption></figure>

### 桌面前向 MSAA 的设置顺序

先在 Project Settings → Rendering 中启用 Forward Shading，按提示重启编辑器，再将 Anti-Aliasing Method 设为 MSAA。UE 5.6 的前向渲染器使用 `r.MSAACount` 调节样本数；切换渲染路径会影响其他渲染功能，应先核对项目需求。[UE 5.6 前向渲染设置](https://dev.epicgames.com/documentation/en-us/unreal-engine/forward-shading-renderer-in-unreal-engine?application_version=5.6)

```ini
; UE 5.6 桌面前向项目：先在项目设置中完成 Forward Shading 配置。
r.AntiAliasingMethod=3
r.MSAACount=4
```

### 方法选择与样本数不是同一个参数

| 参数或取值 | UE 5.6 桌面含义 |
| --- | --- |
| `r.AntiAliasingMethod=0` | 关闭抗锯齿 |
| `=1` | FXAA |
| `=2` | TAA |
| `=3` | MSAA，需要桌面前向路径 |
| `=4` | TSR；该版本控制台变量的默认值，项目仍可覆盖 |
| `r.MSAACount=2 / 4 / 8` | MSAA 样本数 |
| `r.MSAACount=1` | 禁用多重采样 |
| `r.MSAACount=0` | 在相应前向设置下回退到 TAA |

以上值按 [UE 5.6 控制台变量定义](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-console-variables-reference?application_version=5.6)整理。FXAA/TAA 的质量设置不能直接理解为 MSAA 的样本数；移动端也不能仅靠这张桌面表保证运行时切换有效。

### TAA、TAAU 与 TSR 要分开理解

TAA 侧重时间抗锯齿；TAAU 将时间重建与上采样结合，从较低渲染分辨率生成目标分辨率。TSR 是 UE5 的另一套时间超分辨率方案，不能简单当作 TAA 的一个样本数档位。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image53.png" width="639" height="154" alt="TAAU 的管线位置示意：较早提升分辨率，会影响后续 Pass 的处理像素量。" loading="lazy"><figcaption><span>图 27</span> TAAU 的管线位置示意：较早提升分辨率，会影响后续 Pass 的处理像素量。</figcaption></figure>

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image55.png" width="644" height="163" alt="TAA 与后续空间上采样的示意。重点是在哪个阶段改变分辨率，而不是把图中顺序套到所有版本。" loading="lazy"><figcaption><span>图 28</span> TAA 与后续空间上采样的示意。重点是在哪个阶段改变分辨率，而不是把图中顺序套到所有版本。</figcaption></figure>

比较时要同时记录 Render Resolution、Output Resolution 和 Screen Percentage。相同输出尺寸下，较低输入分辨率的 TSR/TAAU 与原生分辨率 FXAA，并没有承担相同的渲染工作量。UE 对这些方法的区分见 [抗锯齿与上采样说明](https://dev.epicgames.com/documentation/en-us/unreal-engine/anti-aliasing-and-upscaling-in-unreal-engine?application_version=5.6)。

## 11 / 性能对照：把抓帧数据读准确

静态截图适合观察轮廓，连续运动用于判断闪烁与拖影，GPU 计时用于判断成本。这三类证据解决不同问题，不能互相替代。

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image59.png" width="1920" height="1040" alt="RenderDoc 中的场景与事件列表，用于定位绘制、资源和后处理阶段。" loading="lazy"><figcaption><span>图 29</span> RenderDoc 中的场景与事件列表，用于定位绘制、资源和后处理阶段。</figcaption></figure>

下面保留一组四帧平均记录，并统一将微秒换算为毫秒。该记录缺少完整硬件、分辨率、引擎版本和计时范围说明，因此仅用于演示数据阅读，不能当作独立 AA Pass 的普遍耗时或当前 UE 的性能排名。

| 方案 | 记录中的平均耗时 | 平均 Event 数 |
| --- | ---: | ---: |
| FXAA | 1.743 ms | 258 |
| TAA | 2.553 ms | 323.2 |
| MSAA 4× | 2.699 ms | 350 |

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image61.png" width="1512" height="720" alt="TAA 的抓帧记录示意。Event 是事件记录，不等于 Shader 指令数。" loading="lazy"><figcaption><span>图 30</span> TAA 的抓帧记录示意。Event 是事件记录，不等于 Shader 指令数。</figcaption></figure>

<figure class="face-figure aa-figure"><img src="/img/anti-aliasing/image62.png" width="1513" height="776" alt="MSAA 4× 的抓帧记录示意。完整影响可能分布在多个阶段，不能只找一个后处理事件。" loading="lazy"><figcaption><span>图 31</span> MSAA 4× 的抓帧记录示意。完整影响可能分布在多个阶段，不能只找一个后处理事件。</figcaption></figure>

**Event 数不能代表 ALU 指令数、纹理采样次数或 GPU 工作量。** 一次 Draw 可以覆盖很少或很多像素，一个事件也可能执行复杂 Shader。抓帧重放还可能影响计时，应结合运行时 GPU 分析工具交叉检查。

### 让对照能够复测

固定相机路径、输出与输入分辨率、曝光、材质、可伸缩性设置和动态分辨率状态。先完成 Shader 编译和资源预热，再采集稳定区间；TAA/TSR 则需等待历史积累，镜头切换后的最初几帧单独观察。

至少分开记录总 GPU 帧时间和相关 Pass 时间，并报告帧数、中位数及波动范围。若为了启用 MSAA 同时从延迟切换到前向，差值包含渲染器变化，不能全部归给 AA。

配套下载提供空白记录表，保留平台、RHI、版本、分辨率、运动场景与计时范围等字段，便于下一次对照使用。

## 12 / 面向实际画面的选择

| 当前最明显的问题 | 优先检查或尝试 | 需要一起观察 |
| --- | --- | --- |
| 前向项目的几何轮廓台阶 | MSAA，结合模型 LOD | 带宽、细几何、材质内部高光 |
| 金属高光与法线细节闪烁 | 材质过滤、粗糙度、TAA/TSR | 运动清晰度、历史有效性 |
| 低成本的单帧边缘平滑 | FXAA，或项目支持的 SMAA 1× | 纹理细节、UI、远处细线 |
| 叶片和毛发卡片硬边 | Mask 过滤、A2C 或相应时序方案 | Alpha Mip、覆盖率与运动稳定性 |
| 面部阴影硬阈值锯齿 | 阈值场质量与 fwidth 边界重建 | 明暗形状、远景宽度、时序变化 |
| 遮挡后出现拖影 | 速度、深度、历史拒绝和曝光匹配 | 新显露区域、动画、镜头切换 |

这里没有固定的画质排行榜。真实几何覆盖、材质高频、透明边界与时序错误需要不同的信息；算法只有拿到合适的信息，才有机会给出稳定的结果。

对卡通角色，我会先检查面部和头发的材质边界，再看武器与服装轮廓，最后让角色转动、镜头拉远。这样更容易分清需要修的是材质、几何、采样，还是历史积累，也能避免用一层越来越强的模糊掩盖所有问题。

<div class="face-download"><strong>配套公式与测试记录表</strong><p>包含四样本 Resolve 与历史裁剪 HLSL 示例、可运行的 CPU 数学演示、原理图生成脚本和空白性能记录表。HLSL 尚未进行 UE 工程内编译；这些片段不构成完整抗锯齿插件。</p><a href="/downloads/anti-aliasing/aa-notes-kit.zip">下载代码与记录表</a><a href="/downloads/anti-aliasing/README.md">查看使用说明</a></div>

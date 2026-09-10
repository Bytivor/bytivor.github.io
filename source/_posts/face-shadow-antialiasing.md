---
title: 卡通角色面部阴影优化：从 SDF 数据到屏幕空间抗锯齿
date: 2022-04-09 16:20:00
permalink: 2026/09/10/face-shadow-antialiasing/
demo_views: 127
demo_likes: 5
updated: 2026-09-10 16:49:54
categories: 卡通渲染
tags: [Unreal Engine, SDF, 抗锯齿, 角色渲染, HLSL]
cover: /img/face-shadow/cover.svg
description: 追踪面部阴影锯齿的来源，拆解纹理压缩、SDF 生成与 fwidth 抗锯齿；结合 14 张实验配图，讲清像素宽度推导、UE 接线与稳定版 HLSL。
toc: true
---

在卡通角色渲染中，面部的明暗处理会直接影响角色的表情与气质。鼻翼的一小块阴影、脸颊分界的一次转折，都可能改变整张脸的观感。因此，面部着色既要让人看出光照方向，也要保持清晰、连贯的明暗块面，让角色在不同角度下都延续设定中的形象。

为了更细致地控制这些阴影形状，我在 UE 的角色渲染实践中使用了面部 SDF 方案：通过一张灰度阈值图描述面部各个位置的明暗变化，再根据光照方向决定阴影边界。这样就可以对鼻子、脸颊等区域单独设计，让光线转动时的明暗过渡更符合卡通角色的表现需求。

基础效果完成后，阴影的大体形状已经符合预期，但近距离观察时，鼻翼和脸颊的边缘仍有明显锯齿。尝试提高纹理质量后，部分台阶得到了改善；继续加入模糊，又出现了局部渗漏。随着镜头拉远，边界的过渡范围还会发生变化，让原本清楚的明暗块面显得发软。

这些现象把问题从“如何画出面部阴影”，推进到了“如何让阴影边缘在不同观察距离下都保持稳定”。下面就从这次排查过程展开，依次检查**阈值图的生成、纹理的存储与采样，以及屏幕像素中的边界重建**，逐步得到一套可控制过渡宽度的抗锯齿实现。

<div class="face-lead"><div><b>01</b><strong>先查数据</strong><p>排除压缩、过滤与阈值图条纹。</p></div><div><b>02</b><strong>再看导数</strong><p>让 fwidth 描述边界附近的变化。</p></div><div><b>03</b><strong>最后定宽度</strong><p>以屏幕像素控制过渡带。</p></div></div>

<figure class="face-figure "><img src="/img/face-shadow/page-09-image-01.png" width="1356" height="969" alt="近、中、远距离的优化前后对照：上排为抗锯齿前，下排为抗锯齿后。" loading="lazy"><figcaption><span>图 14</span> 近、中、远距离的优化前后对照：上排为抗锯齿前，下排为抗锯齿后。</figcaption></figure>

<!-- more -->

<div class="face-callout"><strong>实现目标</strong><p>保留面部明暗块面的清晰形状，把平滑限制在阴影边界附近，同时让近景与远景都保持稳定的阅读感。整个过程分为数据排查、屏幕导数重建与像素宽度控制三个阶段。</p></div>

## 01 / 先确定，锯齿出现在哪一层

### 面部阴影不是普通的 N·L 分段

先看面部 SDF 在材质里承担的具体工作：灰度图为每个 UV 位置保存一个“什么时候进入亮面”的阈值，光照方向则提供与它比较的控制量。两者共同决定明暗边界的位置。

这类资产经常被称为面部 SDF。不过，**从若干张不同光向的黑白 Mask 合成出来的阈值场，不一定满足严格的有符号距离场定义。** 这里沿用 SDF 的常见叫法，但把采样值 S 理解成材质使用的连续控制数据，不直接解释成厘米或纹素距离。

先约定一套本文使用的判定方式：

<div class="face-equation"><code>d = S + L − 1</code><span>S：纹理采样值　·　L：与资产约定一致的光向控制量</span></div>

`d = 0` 是明暗分界；`d > 0` 表示亮面，`d < 0` 表示暗面。最直接的实现为 `step(0, d)`。这能得到干净的两块颜色，却没有表达边界像素被亮面覆盖了多少。

<figure class="face-figure "><img src="/img/face-shadow/page-01-image-01.png" width="977" height="632" alt="初期面部阴影：红框内的鼻翼和脸颊边缘出现明显台阶。" loading="lazy"><figcaption><span>图 01</span> 初期面部阴影：红框内的鼻翼和脸颊边缘出现明显台阶。</figcaption></figure>

### 把问题拆成三层

| 层级 | 典型表现 | 最先检查什么 |
| --- | --- | --- |
| 源数据 | 原灰度图存在条纹、断层，或轮廓本身就是阶梯 | Mask 轮廓、阈值场合成方式、位深 |
| 存储与采样 | 出现压缩块、色阶断裂，远近 Mip 差异很大 | sRGB、实际 GPU 格式、Filter、Mip 与 LOD |
| 屏幕重建 | 数据连续，但阈值切成 0/1 后仍出现锯齿 | 边界函数 d 的导数与屏幕过渡宽度 |

不要一上来就在最终颜色上加模糊。那样会把数据错误、采样错误和重建错误混在一起，难以判断哪一步真正有效。

## 02 / 第一次尝试：九次采样，能解决什么

第一版采用一个 3×3 邻域采样，累加九个采样值后求平均。图像的台阶有所缓和，但成本也从单次采样增加到九次纹理读取。

<figure class="face-figure "><img src="/img/face-shadow/page-02-image-01.png" width="1001" height="618" alt="邻域采样对照：左侧进行了平滑，右侧未进行平滑。" loading="lazy"><figcaption><span>图 02</span> 邻域采样对照：左侧进行了平滑，右侧未进行平滑。</figcaption></figure>

这里需要区分两个相近却不相同的操作：

```hlsl
// A：先平均连续阈值，再做一次判断——阈值图的盒式滤波。
float averagedField = (s0 + s1 + s2 + s3 + s4 + s5 + s6 + s7 + s8) / 9.0;
float resultA = step(threshold, averagedField);

// B：每个样本先判断，再平均——比较结果的覆盖比例。
float resultB = (step(threshold, s0) + step(threshold, s1)
              + step(threshold, s2) + step(threshold, s3)
              + step(threshold, s4) + step(threshold, s5)
              + step(threshold, s6) + step(threshold, s7)
              + step(threshold, s8)) / 9.0;
```

初期命名为 `EasyPcf` 的函数 实际累加的是纹理 R 通道，没有逐样本执行深度比较，因此更准确地说是**九点盒式滤波**。标准 Shadow Map PCF 则平均多个深度比较的结果。两种运算通常不等价。

如果保留九点方案，邻域偏移应由纹理尺寸决定：`OffsetUV = float2(x, y) × InvTextureSize × RadiusTexels`。这样半径明确以纹素为单位，换分辨率后也容易校准。

**成本随采样次数增加，不能笼统写成“几何倍数增长”或“工程中绝对不能用”。** 缓存、硬件比较采样、角色屏幕占比都会影响实际耗时。对于本例，值得继续寻找少量采样就能完成边缘重建的方法。

## 03 / 纹理设置：先保证输入没有被破坏

### 压缩和过滤需要分开做对照

<figure class="face-figure "><img src="/img/face-shadow/page-03-image-01.png" width="851" height="785" alt="纹理设置对比。上图标注 Default + Nearest，下图标注 BC7 + Bi-linear。" loading="lazy"><figcaption><span>图 03</span> 纹理设置对比。上图标注 Default + Nearest，下图标注 BC7 + Bi-linear。</figcaption></figure>

图 03 的改善很明显，但它同时改变了 **Compression Setting 和 Filter**。这只能证明整组设置改善了该案例，不能单独证明 BC7 带来了全部提升。

较可靠的排查顺序是：固定分辨率、Mip 和过滤方式，只换压缩格式；然后固定压缩格式，只换过滤方式。每一步都查看原始灰度值和阈值后的结果。

| 检查项 | 面部阈值图的处理原则 |
| --- | --- |
| sRGB | 它是数值数据，通常关闭 sRGB，避免非线性解码改变阈值 |
| Filter | 用线性过滤作为基线；Nearest 容易直接暴露纹素台阶 |
| Mip / LOD | 固定条件做近景对照，再恢复实际 Mip 链检查远景 |
| 压缩格式 | 按实际通道数选择候选格式，检查烘焙后平台数据 |
| 通道读取 | 使用 Mask / Linear 类数值采样，避免 Normalmap 解码改变数值 |
| 位深 | 确认源图和导入链路没有提前量化，不只看文件扩展名 |

BC4 是单通道块压缩，BC5 适合双通道数据，BC7 面向 RGB/RGBA。它们不是按名称递增的“画质档位”。在相同尺寸下，BC4 为 8 字节/4×4 块，BC5 和 BC7 都为 16 字节/4×4 块；因此不能简单说 BC5 一定比 BC7 更省显存。实际 UE 压缩预设还应结合目标平台检查。

### 输入轮廓已有台阶，压缩无法凭空补回形状

<figure class="face-figure "><img src="/img/face-shadow/page-03-image-02.png" width="1197" height="618" alt="左：阈值图制作阶段的轮廓；右：采样后生成的面部阴影。" loading="lazy"><figcaption><span>图 04</span> 左：阈值图制作阶段的轮廓；右：采样后生成的面部阴影。</figcaption></figure>

提高压缩质量可以减少新增误差，却不能保证恢复源图缺失的轮廓信息。这个阶段应该保存四种调试输出：`S`、`step(0, d)`、`fwidth(S)` 和最终明暗混合。只有把中间结果单独拿出来，才能定位错误来自哪一层。

## 04 / 用屏幕导数，把硬切换变成有限过渡

### fwidth 测到的是什么

在像素着色中，`fwidth(x)` 的定义是 `abs(ddx(x)) + abs(ddy(x))`。它估计这个数值在屏幕 X、Y 方向相邻像素间的变化量；**它不是颜色边缘检测器，也不是阴影 Mask。**

如果边界函数在一个像素附近变化了大约 g，那么覆盖约 W 个屏幕像素的完整过渡带，可以近似取：

<div class="face-equation"><code>g = fwidth(d)</code><code>w = ½ × W × g</code><code>Lit = smoothstep(−w, w, d)</code><span>w 是半宽；从 −w 到 +w 的完整宽度约为 W 个像素。</span></div>

这里的像素宽度是局部近似。`fwidth` 使用 X/Y 绝对导数之和，轮廓朝向也会影响估计；它不保证任意曲率、任意角度下都有完全相同的几何宽度。

<figure class="face-figure compact"><img src="/img/face-shadow/page-04-image-01.png" width="541" height="476" alt="渐变分界示意：利用连续数值重建边界。" loading="lazy"><figcaption><span>图 05</span> 渐变分界示意：利用连续数值重建边界。</figcaption></figure>

![不同像素过渡宽度的 smoothstep 曲线](/img/face-shadow/coverage-width.svg)

*原理图 A：以屏幕位置为横轴，比较硬阈值与不同完整过渡宽度。由解析公式绘制，不是 UE 性能或画面测试。*

`smoothstep` 在过渡区间外返回 0 或 1，区间内使用 Hermite 插值，所以只需在明暗交界处混合亮色和暗色，不必把整张脸都变成连续漫反射。

### 第一版为何仍然渗漏

最初的实现使用类似 `dist / length(float2(ddx(dist), ddy(dist)))` 的方式估计像素距离，再通过 `saturate` 得到覆盖率。问题不只是函数形状：分母接近零时需要保护，输入阈值场中的条纹也会被导数一起检测出来。

<figure class="face-figure "><img src="/img/face-shadow/page-05-image-01.png" width="844" height="551" alt="第一次导数抗锯齿尝试：局部仍有渗漏和不稳定的分界。" loading="lazy"><figcaption><span>图 06</span> 第一次导数抗锯齿尝试：局部仍有渗漏和不稳定的分界。</figcaption></figure>

<figure class="face-figure "><img src="/img/face-shadow/page-05-image-02.png" width="1201" height="540" alt="左为面部阈值图，右为放大后的 fwidth 调试输出。条纹暴露了输入数据的变化。" loading="lazy"><figcaption><span>图 07</span> 左为面部阈值图，右为放大后的 fwidth 调试输出。条纹暴露了输入数据的变化。</figcaption></figure>

图 07 是排查的转折点。`fwidth` 无法知道哪条变化是想要的阴影边界，哪条变化是生成算法留下的条纹。如果输入里存在密集细纹，增加平滑范围可能把它们进一步放大成不希望出现的灰带。

并且，平滑的距离场在远离零等值线的位置也可以存在梯度；不能把“导数只在边界非零”当作所有 SDF 都应满足的条件。真正控制最后一圈过渡的是 **d 与 w 的比较**。

## 05 / 回到源头：让阈值图的生成过程可检查

为了让生成过程可调试，我将不可检查的生成脚本替换为 Substance Designer 中可逐节点查看的流程。先给出不同光向下的黑白 Mask，再通过差分、模糊、缩放和相加形成连续控制图。

<figure class="face-figure "><img src="/img/face-shadow/page-06-image-01.png" width="933" height="97" alt="不同光照阶段对应的黑白 Mask 输入序列。" loading="lazy"><figcaption><span>图 08</span> 不同光照阶段对应的黑白 Mask 输入序列。</figcaption></figure>

<figure class="face-figure "><img src="/img/face-shadow/page-06-image-02.png" width="1368" height="924" alt="Substance Designer 节点图：差分、模糊、分段权重与累加。" loading="lazy"><figcaption><span>图 09</span> Substance Designer 节点图：差分、模糊、分段权重与累加。</figcaption></figure>

读这张图时，可以把操作分成四步：

1. **统一输入。** 所有 Mask 使用相同 UV、尺寸和面部区域，并检查光向变化时轮廓是否按预期推进。
2. **提取相邻阶段的差异。** 差分区域描述两个阶段之间哪些位置改变了明暗状态。
3. **为过渡建立连续数值。** 模糊和权重控制阶段之间如何衔接，每个中间结果都可以单独输出。
4. **合成后检查整张阈值场。** 扫描多个阈值，确认鼻翼、嘴角与脸颊没有孤岛、条纹和非预期回退。

节点图展示了数据流。复现时仍需要按自己的源 Mask 标定模糊半径与权重；本篇配套下载提供 Shader 代码，未包含 `.sbs` 工程。

我尝试了半径为 1、3、5 的均值模糊，并在该案例中取得更干净的结果。这是案例经验，**不代表高斯模糊天然不适合 SDF**：模糊会改变阈值分布，两种核都应以轮廓位置、条纹和时间稳定性来验收。

<figure class="face-figure "><img src="/img/face-shadow/page-06-image-03.png" width="1419" height="612" alt="更换生成流程后的导数对照：左侧杂纹明显减少，右侧为旧流程。" loading="lazy"><figcaption><span>图 10</span> 更换生成流程后的导数对照：左侧杂纹明显减少，右侧为旧流程。</figcaption></figure>

连续场与可变宽度过渡可以用于重建平滑边界，但面部阈值图还要解决光向与阴影形状的美术映射，不能直接套用字体 SDF 的全部假设。

## 06 / 核心实现：先建立不带距离修正的基线

改进后的核心可以简写为：

```hlsl
// 明暗重建核心：FoL 需要满足其上游约定。
FoL = lerp(-0.1, 1.1, FoL);
float w = fwidth(SdfValue) * 2.0;
float Lit = smoothstep(-w, w, SdfValue + FoL - 1.0);
```

`lerp(0, 1, x)` 与 x 相同，所以可以省略。更值得明确的是三个约定：

- 注释中的 `dot(facefront, lightdir)` 自然范围是 −1 到 1，但 `lerp(-0.1, 1.1, FoL)` 是否按 0 到 1 使用，要由上游决定。
- 本文将上游已经解码完成的光向量命名为 **Light01**，明确要求 0 到 1；不要把任意原始点积直接接进去。
- 当光向阈值在屏幕上变化时，使用 `fwidth(d)` 比只对 S 求导更完整；光向量对整张脸为常量时，二者导数一致。

### UE Custom 最小版本

先在材质节点外采样 SDF，把结果送入 Custom。输出设为 `CMOT Float1`，建立三个同名 Float1 输入：`SdfValue、Light01、AAWidthPx`。

```hlsl
// UE Custom expression BODY. Output: CMOT Float1.
// Inputs (Float1): SdfValue, Light01, AAWidthPx.
// No distance compensation. Start with this baseline.
float light = lerp(-0.1, 1.1, saturate(Light01));
float d = SdfValue + light - 1.0;
float w = max(0.5 * max(AAWidthPx, 1.0) * fwidth(d), 1e-5);
return smoothstep(-w, w, d);
```

`AAWidthPx` 从 1～1.5 开始，表示完整过渡带的目标像素宽度。`1e-5` 是数值保护，用来避免 `smoothstep` 的上下界重合；它不是固定的视觉模糊宽度。对于大面积恰好落在阈值上的平坦场，仍需要回到数据制作阶段处理。

把输出作为 `Lerp(ShadowColor, LitColor, Lit)` 的 Alpha。若导入资产的明暗约定相反，只在最终输出处取 `1 - Lit`，避免同时修改贴图、阈值与 Lerp 顺序后失去判断依据。

<figure class="face-figure "><img src="/img/face-shadow/page-07-image-01.png" width="1217" height="836" alt="ScreenAA 前后对照：左侧未使用，右侧使用导数控制的过渡。" loading="lazy"><figcaption><span>图 11</span> ScreenAA 前后对照：左侧未使用，右侧使用导数控制的过渡。</figcaption></figure>

## 07 / 远景发糊：先统一像素单位，再考虑距离曲线

### 为什么镜头远了，导数反而更亮

一个屏幕像素覆盖的纹素范围，会随距离、透视、UV 密度和渲染分辨率改变。因此 `fwidth(S)` 在远景变大，并不自动说明算法错误；它通常是在反映更大的像素覆盖范围。

<figure class="face-figure "><img src="/img/face-shadow/page-08-image-01.png" width="1193" height="497" alt="不同距离下的 fwidth 调试结果：近、中、远景的幅值发生变化。" loading="lazy"><figcaption><span>图 12</span> 不同距离下的 fwidth 调试结果：近、中、远景的幅值发生变化。</figcaption></figure>

先检查完整过渡带是否已用屏幕像素定义。初期实现中的 `w = fwidth(S) × 2` 对应的完整区间是 `[-2g, +2g]`，局部可近似理解为四像素量级；如果预期只有一像素左右，它本身就偏宽。

接着固定 Screen Percentage、抗锯齿模式、Mip 和曝光，分别比较静态截图与镜头移动。只有在这些条件清楚以后，才加入美术上的远景收窄曲线。

### 距离补偿：避免过渡宽度归零

```hlsl
// 早期经验距离项，用于分析边界行为。
float fitted = min(1.0, pow(dist / 1000.0 + 0.8, 2.0));
float w = fwidth(SdfValue) * 2.0 * (1.0 - fitted);
```

当传入的 dist 达到 **200 个输入单位**时，括号里的值为 1，fitted 被夹到 1，最终 w 变成 0。若输入确实是厘米，这对应 200 cm；若上游另做了深度拟合，就不能直接把它解释成真实相机距离。

`w = 0` 会使 `smoothstep(-w, w, d)` 的两个边界重合。它不能作为可靠的“远景关闭模糊”机制，需要保证正宽度并核对输入单位。

![距离补偿权重随输入深度变化的曲线](/img/face-shadow/distance-weight.svg)

*原理图 B：直接计算早期方案的经验权重，展示它在输入 200 处归零的行为。横轴是输入数值，不默认等同于厘米。*

<figure class="face-figure "><img src="/img/face-shadow/page-08-image-02.png" width="781" height="451" alt="引入距离修正后的导数显示。静态对照不能替代对退化输入的检查。" loading="lazy"><figcaption><span>图 13</span> 引入距离修正后的导数显示。静态对照不能替代对退化输入的检查。</figcaption></figure>

### 带可选距离控制的版本

下面的实现默认不随距离缩窄：`FarWidthScale = 1`。确实需要远景收窄时再调低它，同时把目标完整过渡宽度限制在至少 1 像素。这一版进一步加入宽度下限与参数保护。配套代码已完成数学边界检查，尚未完成 UE 工程内编译与 GPU 性能测试。

```hlsl
// UE Custom expression BODY. Output: CMOT Float1.
// Inputs (all Float1): SdfValue, Light01, AAWidthPx, ViewDepthCM,
// NearCM, FarCM, FarWidthScale, MinFieldWidth.
// Pixel stage only. Sample the texture outside this Custom node.
// SdfValue / Light01 conventions must match the authored face threshold field.
float light = lerp(-0.1, 1.1, saturate(Light01));
float d = SdfValue + light - 1.0;
float gradient = fwidth(d);
float t = smoothstep(NearCM, max(FarCM, NearCM + 1.0), max(ViewDepthCM, 0.0));
float nearWidth = max(AAWidthPx, 1.0);
float widthPx = max(1.0, lerp(nearWidth,
    nearWidth * saturate(FarWidthScale), t));
float halfWidth = max(0.5 * widthPx * gradient, max(MinFieldWidth, 1e-6));
return smoothstep(-halfWidth, halfWidth, d);
```

| 参数 | 建议起点 | 含义 |
| --- | --- | --- |
| SdfValue | 纹理采样结果 | 连续的面部阈值数据 |
| Light01 | 上游控制量 | 与资产匹配的 0～1 光向映射 |
| AAWidthPx | 1.5 | 近景完整过渡宽度，单位为渲染像素 |
| ViewDepthCM | PixelDepth 对应的线性深度 | 用于可选距离调节，核对厘米约定 |
| NearCM / FarCM | 100 / 500 | 距离曲线起止点；属于教学初值 |
| FarWidthScale | 1 | 1 表示保持目标像素宽度 |
| MinFieldWidth | 0.00001 | 连续场半宽的数值下限 |

这段代码解决的是宽度约定和退化输入。它不能修好源图中的条纹，也不保证消除所有 TAA/TSR 闪烁或远景细节丢失。

## 08 / 接入 UE：把数据、方向与输出接清楚

### 材质节点的数据流

<div class="face-flow"><span>数值纹理采样 S</span><i>＋</i><span>头部光向 Light01</span><i>→</i><span>Custom：FaceShadowAA</span><i>→</i><span>亮色 / 暗色 Lerp</span></div>

SDF 纹理关闭 sRGB，作为普通数值纹理读取。Custom 的导数运算放在像素路径，不接 World Position Offset；不要把求导放到结果不一致的动态分支里。最终混色可先在 Unlit 材质的 Emissive 上观察，确认正确后再接入已有卡通受光管线。

头部朝向必须随骨骼或头部组件更新。先把光方向投影到与脸部方位约定一致的平面，再依据 FaceForward / FaceRight 求前后和左右关系。左右光向可能需要镜像 UV 或选择不同通道；这是资产制作约定，不属于抗锯齿函数本身。

对没有明确映射说明的资产，先设置四个固定光向验证：正面、左侧、右侧、背面。`0.5 × dot(F, L) + 0.5` 只是常见的线性编码示例；如果贴图按角度阶段制作，实际控制量可能需要角度映射，不能默认互换。

### 一次保存四张调试输出

| 输出 | 观察目标 | 常见异常 |
| --- | --- | --- |
| `S` | 采样后的连续数据 | 压缩块、竖纹、断层 |
| `step(0, d)` | 原始明暗形状 | 阈值方向反转、轮廓本身破碎 |
| `saturate(fwidth(d) × Gain)` | 屏幕变化量 | 大面积杂纹、UV 接缝、异常 Mip |
| 最终 Lit / 颜色 | 过渡带与明暗可读性 | 远景过软、动态闪烁、局部渗漏 |

Gain 只用于方便观察导数，不参与最终着色。在调试输出里看见“白得更亮”，不能直接等同于画面中的模糊更严重；最终结果由 d、w 和屏幕尺度共同决定。

## 09 / 验收：效果与成本，都需要明确条件

导数方案通常无需为了边缘重建再显式增加九次邻域纹理采样，这是它的主要价值。但不能因此说 `fwidth` 完全没有成本，或者保证在任何平台都快于 PCF。像素导数依赖局部着色执行，实际吞吐还会受到材质复杂度、覆盖像素、平台与编译结果影响。

| 测试 | 固定条件 | 重点记录 |
| --- | --- | --- |
| 近 / 中 / 远距离 | 光向、分辨率、曝光一致 | 轮廓可读性与实际过渡宽度 |
| 缓慢转光 | 相机固定 | 阈值连续性、鼻翼是否跳变 |
| 角色转头 | 骨骼与光向更新一致 | 左右切换、UV 镜像接缝 |
| 镜头推进 | 记录 AA 模式和 Screen Percentage | 时序闪烁、Mip 切换、细节消失 |
| 性能对照 | 相同画面与材质覆盖率 | GPU 时间、采样数量、平台信息 |

最有效的排查顺序是：先让源数据可解释，再确认纹理采样没有额外破坏，最后用屏幕像素定义边界过渡。距离曲线是可选的美术控制，不应成为掩盖数据问题的第一步。

<div class="face-download"><strong>配套实现</strong><p>包含最小版与可选距离版 Custom 函数、参数说明、CPU 边界检查和原理曲线的生成脚本。</p><a href="/downloads/face-shadow/face-shadow-aa-kit.zip">下载 HLSL 与说明</a><a href="/downloads/face-shadow/README.md">查看接线说明</a></div>

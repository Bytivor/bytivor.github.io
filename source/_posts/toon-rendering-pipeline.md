---
title: 卡通渲染管线拆解：从 GBuffer 到明暗、阴影与描边
date: 2021-06-18 15:00:00
permalink: 2026/09/10/toon-rendering-pipeline/
demo_views: 186
demo_likes: 8
updated: 2026-09-10 15:00:00
categories: 卡通渲染
tags: [Unreal Engine, Shader, 渲染管线, NPR]
cover: /img/toon-pipeline/stages.svg
description: 沿着一个像素走完 UE 延迟渲染管线，理解自定义着色模型、Ramp 图集、面部法线、投影阴影与屏幕空间描边，并给出可迁移的 HLSL 核心函数。
toc: true
---

把 `N·L` 切成两段，几行代码就能得到卡通色块。但一旦放进真实场景，问题很快出现：天光把暗面提亮，投影阴影把暗色再压黑，换一盏灯颜色就不对，镜头拉远后描边开始闪烁。

要解决这些问题，需要把注意力从一个光照函数，移到整条渲染管线：**哪些数据来自材质，在哪个 Pass 写入，谁读取它，最后又被谁修改。**

这篇笔记沿着“一帧里的一个像素”展开。先理解数据流，再实现明暗、阴影、高光和描边，最后讨论如何接入虚幻引擎。

![同一球体的连续漫反射、明暗分层、高光与轮廓对比](/img/toon-pipeline/stages.svg)

*图 1：原创解析球体示意。图像由本文附带的 Python 脚本按公式生成，不是游戏截图，也不是 UE 实机测试结果。*

<!-- more -->

## 1. 阅读范围与参考关系

本文主要参考 MCKuai 的[《修改虚幻渲染管线的卡通渲染》](https://zhuanlan.zhihu.com/p/23216110797)，以及 0向往0 的[《剖析虚幻渲染体系》开篇与目录](https://www.cnblogs.com/timlly/p/13512787.html)。前者提供自定义着色模型的实践路径；后者帮助定位这些修改在引擎体系中的位置。

需要先划清版本范围：0向往0 在开篇明确说明，其主体分析基于 **UE4.25—4.27 的 PC 延迟管线**。知乎文章讨论了 UE5 中的材质编译、Lumen 等路径。这些材料适合交叉理解设计，不能直接拼成适用于所有 UE 版本的补丁。

本文采用传统 GBuffer / Shading Model 路径讲解，不把它等同于 Substrate 的接入方法。下文的公式、配图、参数布局与 HLSL 核心函数是为教学重新设计的；引擎接线图属于伪代码，需要按项目版本适配。**本文没有在 UE 源码工程中完成编译与性能测试。**

## 2. 一帧里，到底在哪里做卡通化

### 2.1 先区分渲染路径和着色模型

**渲染路径**决定数据与计算怎么安排；**着色模型**决定已知表面和灯光之后，如何计算颜色。卡通风格可以使用前向或延迟路径，也可以混合物理光照与美术规则。

以延迟着色为例：Base Pass 先把可见表面的颜色、法线和材质属性写入 GBuffer；光照阶段读取这些属性，再计算灯光贡献。半透明、后处理等仍有各自的处理环节。可以沿着[延迟渲染管线章节](https://www.cnblogs.com/timlly/p/14732412.html)中的 `FDeferredShadingSceneRenderer`、`BasePass`、`LightingPass` 等入口阅读源码。

![材质、GBuffer、光照、阴影、Ramp 和后处理的数据依赖图](/img/toon-pipeline/pipeline.svg)

*图 2：逻辑依赖图。阴影必须在相应光照使用它之前就绪，但图中的位置不代表引擎的固定调度顺序。*

由这条链可以得到一个直接的调试方法：材质界面里的参数调整无效，不要立即怀疑公式。先确认参数有没有经过编译器进入 Shader，再确认它有没有写入、读出正确的缓冲区。

### 2.2 三种实现方式怎样取舍

| 方式 | 适合解决的问题 | 需要承担的限制 |
| --- | --- | --- |
| 材质内着色 | 单角色验证、Unlit 自定义主光、局部风格实验 | 若自己计算光照，需要额外接入灯光、阴影与环境信息 |
| 屏幕空间后处理 | 深度与法线描边、整体风格滤镜 | 最终颜色通常已经混合了多种光照，难以可靠分离每一项 |
| 自定义 Shading Model / Pass | 独立光照规则、额外数据、与原有材质共存 | 需要维护源码、Shader 变体与不同渲染分支 |

本文的实现顺序是：先用单主光验证风格函数，再把它放进合适的管线位置。一个球体上的阈值都没有调清楚时，增加全套引擎改动只会扩大排查范围。

## 3. GBuffer：先约定数据，再写公式

![颜色、法线、深度、自定义数据的逻辑可视化](/img/toon-pipeline/gbuffer.svg)

*图 3：这些是属性示意，不是 UE 某个版本的 GBuffer 通道截图；深度被重新映射为便于观察的灰度。*

### 3.1 给每个参数一个明确含义

下面是一套本文自定义的最小数据约定。它是“需要传什么”的清单，不是可以覆盖引擎任意通道的授权。

| 逻辑数据 | 范围 / 空间 | 作用 |
| --- | --- | --- |
| BaseColor | 线性 RGB | 表面的基础色 |
| NormalWS | 世界空间单位向量 | 计算光照与法线边缘 |
| Threshold | 0—1 | half-Lambert 的明暗阈值 |
| Feather | 大于 0 | 明暗过渡区的半宽 |
| RampRow | 整数索引 | 选择一套颜色风格 |
| SpecularMask | 0—1 | 限制高光出现的区域 |
| OutlineMask | 0—1 | 控制是否参与描边 |

Normal、Mask、索引是**数值数据**，不应进行 sRGB 颜色解码。BaseColor 是颜色，导入与采样时则应按资产实际色彩空间正确转换。

若把行索引压到一个 8 位 UNORM 通道，可以在写入端存 `row / (rowCount - 1)`，在读取端用 `round(value * (rowCount - 1))` 还原。约束是 `2 ≤ rowCount ≤ 256`；只有一行时直接使用索引 0。不要把 0—1 的归一化值直接当成整数行号。

### 3.2 多加一张纹理，要先算代价

假设新增一张全分辨率 RGBA8 Render Target：

<div class="toon-equation">1920 × 1080 × 4 bytes = 8,294,400 bytes ≈ 7.91 MiB</div>

若每帧完整写一次、读一次，在 60 FPS 下约有 **0.995 GB/s 的逻辑数据量**。这只是未压缩的访问量估算，不是实测显存带宽；缓存、压缩、额外采样和 GPU 架构都会影响实际代价。分辨率变成 3840 × 2160 后，像素数是四倍。

因此先审查已有可用通道、精度与生命周期，再决定是否新增 Toon GBuffer。复用 Metallic 或 Roughness 虽然方便，却会让仍读取它们的反射、间接光或其他路径得到错误语义。

## 4. 明暗分层：把角度变成可控色块

### 4.1 从 half-Lambert 到两段色

约定 `N` 为单位表面法线，`L` 为**从表面指向光源**的单位向量：

<div class="toon-equation">h = saturate(0.5 × dot(N, L) + 0.5)<br>Q = smoothstep(t − s, t + s, h)</div>

`h` 把方向点积映射到 0—1，方便采样 Ramp；它是一种美术控制坐标，不是完整的物理漫反射模型。`t` 控制分界的位置，`s` 控制软边的半宽。`t = 0.5` 对应 `N·L = 0`，阈值越大，亮面通常越小。

![连续曲线、硬阈值、平滑阈值对比](/img/toon-pipeline/threshold.svg)

*图 4：为了看清过渡，图中使用 s = 0.08；球体对比使用更窄的 s = 0.02。*

下面的 HLSL 是独立的数学核心。输入向量须已归一化，`pixelWidth` 由调用端提供；这样函数自身不依赖某个引擎的光照结构体。

```hlsl
float ToonBand(float h, float threshold, float feather, float pixelWidth)
{
    float width = max(max(feather, 0.5 * pixelWidth), 1e-4);
    return smoothstep(threshold - width, threshold + width, h);
}

float HalfLambert(float3 N, float3 L)
{
    return saturate(0.5 * dot(N, L) + 0.5);
}
```

在具有有效导数的像素着色器中，可以把 `fwidth(h)` 传给 `pixelWidth`。它估计像素邻域中的变化量，帮助避免分界过窄。[Microsoft 的 fwidth 文档](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-fwidth)给出了 `abs(ddx(x)) + abs(ddy(x))` 的定义。

导数应在适当的、一致执行的像素路径里计算。不要把这段调用直接搬进任意 Compute Shader，或假定材质边界上的导数总是可靠。这里的软化只能处理局部分界，不能代替完整的时域抗锯齿。

### 4.2 Ramp 把“亮暗比例”提升为“颜色设计”

两段色可以写成 `lerp(ShadowColor, LitColor, Q)`。如果想让过渡区域偏红、暗面偏紫，或者衣服和皮肤使用不同色阶，就让光照坐标去查颜色表：

<div class="toon-equation">C<sub>ramp</sub> = Ramp(h, row)</div>

![三行 Ramp 图集与行中心采样坐标](/img/toon-pipeline/ramp.svg)

知乎文章通过 Curve Atlas 管理不同 Ramp。Epic 的[Curve Atlases 文档](https://dev.epicgames.com/documentation/en-us/unreal-engine/curve-atlases-in-unreal-engine-materials)也说明了把多条颜色曲线放入纹理的机制。下面给出一个更容易看清采样规则的教学版本：**每个 Ramp 占恰好一行，使用 LOD 0。**

```hlsl
float3 SampleToonRamp(Texture2D<float4> atlas,
                      SamplerState linearClamp,
                      float h, uint row,
                      uint width, uint rowCount)
{
    // Preconditions: width >= 2, rowCount >= 1; texture size matches.
    row = min(row, rowCount - 1);
    float u = (0.5 + saturate(h) * (width - 1)) / width;
    float v = (row + 0.5) / rowCount;
    return atlas.SampleLevel(linearClamp, float2(u, v), 0).rgb;
}
```

`u` 从首个 texel 的中心走到最后一个中心，`v` 固定在某行中心。这样既能横向插值，也不会无意混入相邻行。实际图集若有行间留白或一条曲线占多行，应改用真实的行中心映射。

这个教学布局选择固定 LOD，避免 mip 把不同 Ramp 混合；代价是缩小时不会自动获得合适的预过滤。生产中可以使用带 padding 的图集、纹理数组或专门生成的 mip，并检查远距离闪烁。Ramp 表示颜色还是数值，也要在导入时约定清楚，避免重复 gamma 转换。

## 5. 阴影：形体明暗和遮挡信息要分开

`N·L` 回答“表面朝向光吗”；Shadow Map 回答“光到这里的路被挡住了吗”。两者不是同一个问题。

![形体分层、投影可见性、两者相乘的对比](/img/toon-pipeline/shadow.svg)

*图 6：示意中的 V 来自人工构造的遮挡边界，目的是展示合成规则，不模拟完整 Shadow Map。*

### 5.1 阴影只在约定的位置参与一次

令 `V = 1` 表示可见光源，`V = 0` 表示完全遮挡。对于一个**只评估一次的单主光风格合成**，可以定义：

<div class="toon-equation">W = Q × V<br>C = lerp(C<sub>shadow</sub>, C<sub>lit</sub>, W)</div>

这里的暗色是美术指定的基底，不会因为直射光被遮挡就必然变成纯黑。这个选择便于角色风格控制，也意味着它不是能量守恒的 BRDF。

```hlsl
float3 ComposeToonKey(float3 shadowColor, float3 litColor,
                      float band, float visibility)
{
    float weight = saturate(band) * saturate(visibility);
    return lerp(shadowColor, litColor, weight);
}
```

若 `V = 0.5` 已经参与一次合成，外层又把整个结果乘以 `V`，暗色也会被压低。对于单独的光照贡献，重复乘法还会把 `0.5` 变成 `0.25`。这就是为什么修改 BxDF 之前，要检查它的调用者是否已经应用了阴影与距离衰减。

**这段 `ComposeToonKey` 不能原样放进逐灯累加函数。** 若每盏灯都返回一份 `shadowColor`，灯越多，基底就越亮。本文建议把基底 / 环境项只计算一次，各灯只累计直接光贡献；或者明确指定一个负责色块的主光，让补光使用另一套受控规则。

### 5.2 “去掉自阴影”不等于“保留外部投影”

面部希望保留头发投影，却抑制鼻翼与面颊的小块自阴影时，直接把最终 `SurfaceShadow` 设为 1，通常会同时丢掉外部遮挡。一个已经合并的可见性标量，并不包含完整的“是谁投下了这片阴影”的身份信息。

要做选择性接收，需要额外设计：例如单独的角色阴影、头发到面部的遮挡数据，或在阴影生成阶段保留分类信息。它是资产与管线问题，不能只靠改一个乘号完整解决。

### 5.3 PCF 和模糊阴影结果，发生的位置不同

知乎文章对屏幕空间 LightAttenuation 的采样进行平滑。这里要进一步区分两个操作：

| 操作 | 输入 | 实际发生的事情 |
| --- | --- | --- |
| PCF | 光源视角的深度图、接收点深度 | 多次深度比较，再过滤比较结果 |
| 屏幕空间阴影滤波 | 已经生成的可见性 / 衰减纹理 | 平滑屏幕上的阴影结果 |

两者都可能让边界柔和，但后者会在遮挡关系变化处混合不同表面，需要深度或法线引导。不能把普通颜色纹理的双线性采样，直接称作完整的 Shadow Map PCF。

下面是一个通用 3×3 PCF 核心，**不针对 UE 的 VSM 或具体阴影图布局**。它约定普通深度越近越小，比较采样器使用 `LESS_EQUAL`；`uv` 与 `receiverDepth` 已完成光源投影，图集边界和投影视锥外的处理由调用端负责。

```hlsl
float PCF3x3(Texture2D<float> shadowMap,
             SamplerComparisonState cmpLessEqual,
             float2 uv, float receiverDepth,
             float2 invShadowSize, float bias)
{
    float sum = 0.0;
    [unroll] for (int y = -1; y <= 1; ++y)
    {
        [unroll] for (int x = -1; x <= 1; ++x)
        {
            float2 offset = float2(x, y) * invShadowSize;
            sum += shadowMap.SampleCmpLevelZero(
                cmpLessEqual, uv + offset, receiverDepth - bias);
        }
    }
    return sum / 9.0;
}
```

比较采样的核心是先得到深度测试结果再过滤，可对照[Microsoft SampleCmp 文档](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-samplecmp)。若使用 reversed-Z，比较方向与 bias 符号必须配套调整。bias 过小易自遮挡，过大则可能让阴影脱离物体；增加采样次数不会自动解决这两类问题。

## 6. 面部：让法线服务于美术形状

知乎文章的面部方案采用“基础方向 + 细节法线”的思路，避免直接依赖面部几何产生碎小阴影。这与许多仅按水平光向查询的 Face SDF 方案不同：前者修改参与点积的方向，后者修改光向到阴影形状的映射。

本文把这个思路整理成四步：建立随头部运动的方向基底；把美术控制方向转换到约定空间；在同一空间混合细节；最后归一化并进入光照计算。

```hlsl
float3 FaceNormalFromBasis(float3 detailTS,
                           float3 faceRightWS,
                           float3 faceUpWS,
                           float3 faceForwardWS)
{
    // Basis must be orthonormal and follow the animated head.
    float3 n = detailTS.x * faceRightWS
             + detailTS.y * faceUpWS
             + detailTS.z * faceForwardWS;
    return normalize(n);
}
```

这段代码做的是**基底变换**，不是通用的两张法线贴图混合算法。`detailTS` 必须已经解码为 −1 到 1 的方向，并按这个面部基底制作；如果直接使用常规网格切线空间贴图，就必须处理网格 TBN 与面部基底之间的关系。

特别注意骨骼动画：角色 Actor 的前方向不一定等于头部前方向。转头后阴影仍停留在原位置，常见原因就是用了错误的变换层级。非均匀缩放下，法线变换也不能机械地使用普通位置矩阵。

## 7. 高光与边缘光：各自有各自的职责

高光描述局部的反射特征，边缘光强调轮廓。把二者都简单调亮，容易把塑料、金属和布料变成同一种质感。

一个方便实验的高光模型是先计算 Blinn–Phong 形状，再把亮斑分层：

<div class="toon-equation">H = normalize(L + V<sub>view</sub>)<br>P = max(dot(N, H), 0)<sup>exponent</sup><br>S = smoothstep(k − f, k + f, P)</div>

```hlsl
float ToonSpecular(float3 N, float3 L, float3 viewDir,
                    float exponent, float threshold, float feather)
{
    float3 sum = L + viewDir;
    float len2 = dot(sum, sum);
    if (len2 < 1e-6) return 0.0;
    float3 H = sum * rsqrt(len2);
    float p = pow(saturate(dot(N, H)), max(exponent, 1.0));
    float f = max(feather, 1e-4);
    return smoothstep(threshold - f, threshold + f, p);
}
```

`exponent` 越大，高光通常越集中；`threshold` 改变亮斑的保留范围。最后还应乘上高光 Mask、适当的受光限制和阴影可见性。第一张球体图用这个思路展示了亮斑，但它不包含金属 Fresnel、各向异性或真实布料微表面模型。

边缘光则可从 `1 − saturate(N·Vview)` 开始，再用主光方向和部位 Mask 限制。屏幕空间深度偏移也能得到轮廓附近的亮带，但会受画面外物体、遮挡、分辨率与深度不连续影响。无论哪条路线，都应先说明自己要的是受光轮廓还是全方向装饰线。

## 8. 屏幕空间描边：找到值得保留的边缘

![深度、法线和对象选择共同决定描边](/img/toon-pipeline/outline.svg)

知乎文章组合了深度 Sobel、深度 Laplacian 和法线 Laplacian。本文给出一个更小的四邻域版本，方便独立观察深度边缘与法线边缘的职责。

设中心正值线性视空间深度为 `z0`，邻居为 `zi`；法线均已解码、归一化且处于同一空间：

<div class="toon-equation">E<sub>depth</sub> = max<sub>i</sub> |z<sub>i</sub> − z<sub>0</sub>| / max(z<sub>0</sub>, ε)<br>E<sub>normal</sub> = max<sub>i</sub> (1 − dot(N<sub>0</sub>, N<sub>i</sub>))</div>

```hlsl
float2 EdgePair(float centerDepth, float neighborDepth,
                 float3 centerNormal, float3 neighborNormal)
{
    float dz = abs(neighborDepth - centerDepth)
             / max(centerDepth, 1e-3);
    float dn = 1.0 - clamp(dot(centerNormal, neighborNormal), -1.0, 1.0);
    return float2(dz, dn);
}
```

调用端分别采样上下左右，对返回的两个分量各取最大值，再用各自阈值生成 0—1 权重。这个算子用于教学；它不是 Sobel 的等价实现，也可能在线条方向上有偏差。

三个工程细节会直接影响成片质量：

1. **采样步长按像素定义。** `offsetUV = direction × radiusPx / textureSize`。若纹理包含视口子区域，还需要使用正确的 ViewRect / SceneTexture UV 映射。
2. **分开控制两种边缘。** 法线贴图的细小起伏可能产生大量黑线，可以改用平滑法线、降低权重或用材质 Mask 排除脸部。
3. **显式处理背景与遮挡。** 无有效深度的天空不能拿来参与普通相对深度差；CustomDepth 描边还应按需求与 SceneDepth 比较，避免把被遮住的对象画到前景上。

固定像素宽度的描边，在物体远离后占据的物体相对比例会变大，不一定是线条的绝对像素数增加。远距离调权重、减小采样半径或逐渐淡出，是三种不同的控制，不应混为一谈。

## 9. 接入 UE：沿数据链修改，而不是背文件清单

MCKuai 的文章把修改分布在材质注册、编译环境、GBuffer 写入和光照分发等位置。下面按职责重新组织，文件名只作为**查找入口**；你的分支可能已经移动、拆分或替换了它们。

| 职责 | 可搜索的入口 | 最先验证什么 |
| --- | --- | --- |
| 模型注册与编辑器显示 | `EMaterialShadingModel`、`GetShadingModelString` | 新材质能选到模型，保存后仍保留 |
| 编译条件与材质引脚 | `GetMaterialEnvironment`、`IsPropertyActive_Internal` | 正确的宏、输入和默认值进入 Shader |
| 自定义数据写入 | `WRITES_CUSTOMDATA_TO_GBUFFER`、`ShadingModelsMaterial.ush` | 写入一个已知常量，再原值读回 |
| 着色模型分发 | `ShadingModels.ush`、`IntegrateBxDF` | 仅自定义材质走新分支 |
| 逐灯与阴影累加 | `DeferredLightingCommon.ush` | 灯色、衰减、阴影各参与几次 |
| 环境与反射路径 | 天光、间接光合成、反射相关 Shader | 不再被默认贡献意外提亮 |
| 调试工具 | Pixel Inspector、Buffer Visualization | 能看到正确的模型 ID 与数据 |

下面是本文单主光实验的接线伪代码。它描述的是一个合成阶段，不是 UE BxDF 的函数签名。

```cpp
// Pseudocode: project-specific sampling/binding functions are omitted.
surface = ReadSurfaceData(pixel);
key     = ReadSelectedKeyLight(pixel);
q       = ToonBand(HalfLambert(surface.N, key.L), t, s, pixelWidth);
v       = ReadKeyLightVisibility(pixel);

// Evaluate the art-directed baseline once per pixel.
color = ComposeToonKey(shadowColor, litColor, q, v);
color += specularColor * specularMask * specularWeight * q * v;

// Optional fill and environment are independently controlled.
color += EvaluateFillLightsAndEnvironment(surface);
WriteLinearSceneColor(pixel, color);
```

若改为逐灯 BxDF，必须重新划分“每像素一次”和“每盏灯一次”的计算，并使用该版本规定的光照累加约定。不能把一张单主光演示图成功，视为点光、聚光、Clustered / Tiled 分支都已经接通。

同样，增加 Shading Model ID 之前，应检查当前版本的编码位数、保留值和模型上限。增加一张 GBuffer 纹理不会自动修改所有 ID 打包、解码与分发逻辑。

## 10. 后处理会再次改变你设计的颜色

得到线性场景颜色之后，曝光、色调映射、Bloom 和时域处理仍可能影响最终效果。蓝色暗面变灰、白色高光糊成一片，不一定是 Ramp 或高光公式错误。

本文建议调试时先固定曝光，逐个开关后处理。描边放在时域处理之前，通常更容易参与抗锯齿，但也要检查运动历史造成的拖影；放在最终图像之后则更直接，却可能保留像素级抖动。Epic 的[后处理材质文档](https://dev.epicgames.com/documentation/en-us/unreal-engine/post-process-materials-in-unreal-engine)解释了插入位置、GBuffer 读取、UV 与时域抖动的关系，具体位置名称应以项目版本为准。

不要通过对最终 SceneColor 做逐通道除以 BaseColor，假定能完整还原“纯光照”。反射、自发光、色调映射以及接近零的底色都会破坏这种推断。

## 11. 按这个顺序做验证

| 阶段 | 固定条件 | 通过标准 |
| --- | --- | --- |
| 数据链 | 常量颜色、常量参数 | GBuffer 读回与预期一致 |
| 明暗 | 单主光、固定曝光、无投影 | 转动灯光，分界连续且方向正确 |
| 阴影 | 添加独立遮挡物 | 暗面不被重复压黑，遮挡仍有效 |
| 面部 | 头部旋转、角色整体旋转 | 控制方向跟随正确骨骼 / 坐标空间 |
| 多灯 | 方向光、点光、聚光逐个加入 | 基底不随灯数重复增加，各路径一致 |
| 描边 | 近远镜头、遮挡交叉、动态分辨率 | 无明显串边、背景黑线或线宽突变 |
| 时域 | 运动镜头、动画、不同屏幕占比 | 检查闪烁、拖影与细线消失 |
| 性能 | 目标设备与实际场景 | 记录新增 Pass、纹理和 GPU 时间 |

这些是接入 UE 后的验收步骤，不是本文已经完成的实测清单。本次配图验证的是公式和数据关系；是否适合生产，还需要在真实资产、目标平台与实际引擎版本中判断。

## 12. 从最小实现开始扩展

第一轮只需要一个球、一盏光、两种颜色和一条可以观察的分界。第二轮加入遮挡物，确认阴影不会重复作用。第三轮换成角色，处理面部方向和材质差异。最后再接入描边、补光与环境效果。

卡通渲染的关键在于建立一组可预测的规则：美术知道哪个参数控制哪块画面，程序知道这个参数经过哪条数据链，排错时能把异常定位到某个阶段。规则稳定之后，再增加效果才不会互相抵消。

### 资料与下载

- [下载本文 HLSL 数学核心](/downloads/toon-pipeline/ToonCore.hlsl)：包含明暗、Ramp、阴影、高光、法线与边缘计算；不是完整 UE 插件。
- [下载原创配图生成脚本](/downloads/toon-pipeline/generate-toon-figures.py)：Python 标准库生成 SVG 与内嵌 PNG；博客源码中的原版位于 `tools/`。
- [MCKuai：修改虚幻渲染管线的卡通渲染](https://zhuanlan.zhihu.com/p/23216110797)，页面标注更新于 2025-04-20。
- [0向往0：剖析虚幻渲染体系—开篇说明](https://www.cnblogs.com/timlly/p/13512787.html)；延伸阅读[延迟管线](https://www.cnblogs.com/timlly/p/14732412.html)、[光源与阴影](https://www.cnblogs.com/timlly/p/14817455.html)、[Shader 体系](https://www.cnblogs.com/timlly/p/15092257.html)。

本文为基于公开资料的独立学习整理。配图、核心函数与示例参数为本文重新制作；引擎源码定位来自参考资料，不代表官方接口承诺。原作者的截图和完整代码未在本文转载。

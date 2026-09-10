# UE Hosiery Kit

原创教学用材质函数与程序贴图。未经过 Unreal Engine 编译或 GPU 实测，不含角色模型、uasset 或第三方教程图片。

## 自定义节点

文件内容直接粘贴到 Custom 节点 Code，不能再包一层函数。

- HosieryColor.hlsl：Float3 输出；输入 SkinColor(float3)、YarnColor(float3)、Coverage(float)、TauRGB(float3)、MacroNormalWS(float3)、ViewWS(float3)、MuFloor(float)。输出接 Base Color。传统基线 Surface / Opaque / Default Lit。Metallic=0，Specular 默认，Roughness=.44。
- SafeTangent.hlsl：Float3 输出；输入 DirectionWS(float3)、NormalWS(float3)。输入法线必须非零；输出世界空间切线。Flow RG 先乘2减1、补Z=0，再 TransformVector Tangent→World。输出按材质空间设置转换后接 Tangent。
- FilteredGrid.hlsl：Float2 输出；输入 P(float2，连续周期坐标)、Duty(float，线宽比例)。R 为覆盖、G 为周期/像素足迹。使用像素导数，不能用于 WPO。远景平均覆盖不等于 Masked 的正确裁剪，需处理 LOD。

## 贴图

八张 PNG 均为1024²。Coverage、Density、Roughness、Flow、Reinforcement 关闭 sRGB；Normal 选择 Normalmap 压缩和 Normal 采样。Flow不是法线。Knit纹理与网格蕾丝纹理为可平铺结构示意；Reinforcement 的 V 方向使用 Clamp。

平面/圆柱：先以 UV0 验证。T_Knit_* 每个贴图块包含8组周期，不要再次误当成只有一根线。角色区域遮罩和UV需另行适配。法线绿通道需在目标模型上检查。

## 生成与检查

Python 3 + numpy + Pillow + matplotlib。
`python verify_math.py` 运行数学边界检查。
`python generate.py --out ./generated` 生成图表与贴图。系统需有中文字体（可用环境变量 HOSIERY_FONT 指定字体文件）。

benchmark.csv 是空白实测记录模板，所有 GPU 数据必须在目标 UE 工程里测量后填写。

图表是程序示意，不是 UE 渲染截图。参数是艺术起点，非测量数据或 D 数换算。

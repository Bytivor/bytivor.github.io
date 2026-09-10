# 实时渲染抗锯齿配套笔记

配套文章：https://bytivor-blog.ecatcx.chatgpt.site/2026/09/10/anti-aliasing-msaa-taa/

- Resolve4x.hlsl：读取四样本颜色纹理并等权 Resolve 的独立像素着色器示例，需要图形接口层绑定资源。
- ClipHistory.hlsl：从颜色 AABB 中心沿历史颜色方向裁剪的辅助函数。输入颜色空间必须一致，Lo/Hi 来自当前邻域。
- aa-math-demo.cjs：可运行的 CPU 数学示例，检查 Resolve、裁剪、指数积累与二值边缘编码。
- generate-figures.py：使用 NumPy 和 Matplotlib 生成解析曲线及采样封面。
- performance-log.csv：空白性能记录表，没有预填虚构测量。

运行数学示例：`node aa-math-demo.cjs`。

生成原理图：`python generate-figures.py figures`，需要 numpy、matplotlib。

这些代码不是完整 TAA、FXAA 或 MSAA 插件，也不是 .uproject。HLSL 尚未进行 UE 工程内编译或 GPU 性能测试，CPU 检查不能替代引擎验证。

Resolve 示例要求像素坐标与输入纹理一一对应，并绑定四样本颜色资源；深度 Resolve 不应直接平均套用。历史裁剪函数不包含速度解码、深度有效性、曝光匹配和历史纹理生命周期管理。

性能表应记录硬件、驱动、RHI、引擎版本、渲染路径、输入/输出分辨率、方法、预热与采样帧数、计时范围。RenderDoc Event 数不是着色器指令数。图中的采样分布为教学示意，不代表某款 GPU 固定样本布局。

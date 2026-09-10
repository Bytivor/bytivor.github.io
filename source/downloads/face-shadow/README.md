# 面部阴影抗锯齿：UE Custom 教学代码

文章：https://bytivor-blog.ecatcx.chatgpt.site/2026/09/10/face-shadow-antialiasing/

## 接线

在像素材质路径使用 Custom，输出 CMOT Float1。纹理在外部采样为数值，不启用 sRGB。
先运行 Minimal 版本：输入 SdfValue、Light01、AAWidthPx，Float1。
Light01 是上游按资产约定解码后的 0..1 光向量，不是未经转换的点积。
返回值为亮面权重；接 Lerp(ShadowColor, LitColor, Lit)。
正式接入已有光照模型前，可在 Unlit 的 Emissive 上观察。

扩展版另接 ViewDepthCM、NearCM、FarCM、FarWidthScale、MinFieldWidth。
默认值：AAWidthPx=1.5，NearCM=100，FarCM=500，FarWidthScale=1，MinFieldWidth=0.00001。
FarWidthScale=1 时不进行距离收窄。ViewDepthCM 需要正的线性视空间深度。
宽度以渲染像素为单位，Screen Percentage 和时序 AA 会影响最后的观感。

## 验证与限制

`node check-boundaries.cjs` 检查CPU 计算的有限性、明暗单调性和宽度退化边界。
CPU 检查不运行 ddx/ddy，不等于 UE Shader 编译、实际节点验证或 GPU 性能测试。
本包没有 UE 工程、角色资产、源 SDF 纹理或 Substance Designer 工程。

## 配套内容

Bytivor《卡通角色面部阴影优化》的配套实现，包含两版 Custom 函数与曲线生成脚本。
图表生成需 Python、numpy、matplotlib；执行 generate-plots.py 后在当前目录输出两个 SVG。

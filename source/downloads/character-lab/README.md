# UE 战双风格角色材质练习包

配套文章：https://bytivor-blog.ecatcx.chatgpt.site/2026/09/10/ue-toon-character-lab/

本包提供分段漫反射、高光、边缘光与描边的 UE 材质搭建步骤。

本包不是 .uproject，不含原角色模型、游戏贴图、编译后的材质或生产级引擎补丁。
HLSL 尚未在 UE 中编译。CPU 数学验证不能代替引擎测试。
面向 UE5 桌面传统材质路径；Substrate 与具体渲染版本需要另行接入。

## 使用方式

1. 创建 Surface / Opaque / Unlit 主材质。手工计算颜色接到 Emissive。
2. 每个 .custom.hlsl 文件是一个 Custom 节点的函数体，直接粘贴到 Code。
3. 按文件头的 Inputs 建立同名输入；按下表设置输出。
4. Normal 贴图转换为世界空间再送入高光；所有方向输入必须非零。
5. L 为表面指向灯光；V 为表面指向相机。光源可见性原型先设为 1。
6. 逐步输出明暗权重、高光、边缘 Mask，确认后再合成。

| 文件 | 输出 | 连接 |
| --- | --- | --- |
| DiffuseWeight.custom.hlsl | CMOT Float1 | 暗色／亮色 Lerp 的 Alpha |
| GGX.custom.hlsl | CMOT Float3 | PBR 镜面 BRDF，未乘光色、NoL 或阴影 |
| BlinnPhong.custom.hlsl | CMOT Float3 | 美术高光，未乘光色、NoL 或阴影 |
| DepthRim.custom.hlsl | CMOT Float1 | Post Process 中的 RimMask |
| OutlineWPO.custom.hlsl | CMOT Float3 | 额外轮廓网格材质的 World Position Offset |

## 通道和合成

- BaseColor：RGB 颜色，采样后在线性空间计算。
- LightMap：R 偏移编码，本文以 0.5 为中性；G 漫反射遮蔽；B 总高光 Mask。
- PBRMask：R 金属度；G 光滑度；B 高光遮蔽；A 高光混合。
- VertexColor：A 宽度；B 控制沿相机前向的描边偏移。
- 数值 Mask 关闭 sRGB；彩色 Ramp 使用与创作空间一致的 sRGB 设置，Clamp 寻址。
- Roughness = 1 - PBRMask.G。本文 GGX 采用 alpha = Roughness²。
- BP 与 GGX 混合后，再乘 SpecMask、KeyColor、KeyIntensity、saturate(N·L)、Visibility。
- toon diffuse 已经分类，不要无条件再乘一次 NoL。
- 原型的 KeyIntensity 是归一化美术参数，不能直接等同于方向光的 lux。

## 深度边缘光接线

Post Process 材质采样 SceneTexture:SceneDepth 的中心和四邻域深度。
UV 和 InvSize 必须对应深度纹理；邻居限制在当前视图有效像素区域。
这里期望正的线性视空间深度 cm，不是原始 Device Z 或欧氏距离。
已线性化的 SceneDepth 不需要再次进行深度解码。
先用相机正前方 300 cm 平面核对输入单位。

VisibleCharacterMask = (CustomStencil == 7) * (abs(CustomDepth - SceneDepth) < ToleranceCM)。
场景遮挡必须参与判断。角色主网格写入带 Stencil 的 CustomDepth。
DepthRim 不直接采样纹理，所有纹理读取通过材质节点在外部完成。
结果叠加到 PostProcessInput0，再输出 Emissive。
确认所选后处理位置的纹理可用性、曝光空间与时序处理顺序。

## 描边接线

额外 OutlineMesh 复制主体骨骼网格与变换，用 Set Leader Pose Component 跟随主体。
Surface / Masked / Unlit，Two Sided 开启。
Opacity Mask = saturate(-TwoSidedSign) * step(0.0001, VertexColor.A)，Clip Value = 0.5。
零膨胀仍有壳面，因此必须同时屏蔽 A=0 区域，避免共面重叠黑块。
WPO 使用顶点法线、顶点色和当前相机世界基底。
关闭轮廓组件 Cast Shadow、碰撞与 CustomDepth 写入。
WidthCM 单位厘米；相机基底必须正交归一，Forward 指向场景。
默认 DepthBias = 0。B=1 取消深度偏移，A=0 取消膨胀。
相机 MPC 只演示单相机情况。另行检查 Bounds、LOD、Morph、布料与动画同步。

## 验证

安装 Node.js 后，在本目录执行：

    node check-math.cjs

此脚本检查 CPU 参考公式的单调性、GGX 互易性和退化方向、深度遮挡与描边边界。
它不验证 UE 编译、材质节点实际接线、CustomDepth 时序或 GPU 性能。
本文数值均为教学初值，未声称为原游戏参数。

## 许可

配套代码以 CC BY-NC-SA 4.0 分享。角色与资产权利归相应权利人。
https://creativecommons.org/licenses/by-nc-sa/4.0/

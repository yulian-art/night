# 向星而行 · 角色 3D 资产

用 Blender 5.1 手工建模的首批角色资产，严格按《向星而行》设计文档的配色与「圆润低模、温暖童话感」风格。

## 文件

| 文件 | 部件数 | 说明 |
|---|---|---|
| `astronaut.glb` | 16 | 主角宇航员（小小旅人）：大白头盔 + 深蓝大面罩（金色描边）、生命维持背包（金色发光条）、橙色围巾 |
| `fox.glb` | 15 | 拾光狐狸（带路伙伴）：大三角耳朵、蓬松大尾巴带奶白尾尖、奶白胸毛 |
| `starjourney_heroes.blend` | — | Blender 源工程（两角色 + 灯光场景），供继续编辑细化 |

## 导入 UE

`glb` 可直接拖入 UE 5.8 内容浏览器（glTF 导入插件，UE5 内置），或放入工程 `Content/` 后由引擎识别。模型按公制（米）建模；导入 UE 时注意缩放（Blender 1 单位 = 1 m，UE 1 单位 = 1 cm，必要时按 ×100 缩放）。材质随模型自带，为纯色 + 自发光，符合设计文档「低细节轮廓、冷色大环境 + 暖色小焦点」。

## 当前状态与后续

- 两个角色为**静态低模**（部件拼装），**尚未绑骨骼、无动画**。跑步 / 换道 / 蹲下 / 摇尾巴等需要后续绑 rig + 制作动画。
- 待建资产：云鲸、任务机关（邮站 / 风车 / 信封 / 路灯 / 花台）、场景件（树 / 石 / 蘑菇 / 云桥 / 巨行星 / 群山剪影）。

## 参考资产（第三方，见 `reference/`）

针对上面「尚未绑骨骼、无动画」这一条，网络上检索到了可直接用的**已绑定带动画**替代件：

| 文件 | 授权 | 骨骼 / 动画 | 用途 |
|---|---|---|---|
| `reference/models/astronaut_Quaternius_3hC2i0CTuO.glb` | **CC0** | 已绑定 / **24 段** | 真 T-pose 宇航服人形，网格名 `SpaceSuit_Feet/Legs/Body/Head`，**可直接进引擎跑** |
| `reference/models/quaternius_fox_cc0.glb` | **CC0** | 已绑定 / **12 段** | 四足赤狐，Walk / Gallop / Idle / Attack / Eating / Jump |
| `reference/models/astronaut_PW-Wu_erlAEWfFKH3.glb` | CC-BY 3.0 | 无 / 无 | 外形最接近设计稿，但**姿势已烘进网格**、且拆成 89 个 mesh，不适合直接绑定 |
| `reference/models/astronaut_Poly-by-Google_dLHpzNdygsg.glb` | CC-BY 3.0 | 无 / 无 | 经典白宇航员，静态，可作外形参照 |

同目录另有 8 个候选的对比图（`reference/01…04_*.png`）与完整检索清单
（`reference/README.md`、`reference/models/README.md`）。

> ⚠️ **授权**：CC0 无署名义务；**CC-BY 必须署名原作者**（PW Wu / Poly by Google 等）。
> 商用或参赛提交前请按清单核对署名。
>
> ⚠️ 这些是**第三方参考件**，不是本项目原创资产；若要作为最终交付物，
> 建议只取 CC0 那两个，或按 CC-BY 要求补署名。

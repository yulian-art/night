# 「向星而行」角色 3D 模型网络检索清单

> 检索日期：2026-09-22
> 参照图：三张关卡概念图（01 风邮原野 / 02 回声森林 / 03 云鲸星海），角色为
> **Q 版宇航员小孩（白宇航服 + 圆头盔黑面罩 + 金色围巾 + 背包）** 与
> **橙色赤狐（四足、白胸白尾尖、戴鞍具/背带）**。

## 结论先说

1. **不存在与概念图完全一致的现成模型。** 参照图是 AI 生成的关键视觉（三张关卡卡牌、
   右上角 ★024 计数），属于美术方向稿，不是任何已发布资产。
2. **但方向对得上的免费模型是有的**，下面按「人」「狐」分开列，均已逐一看图核实
   （不看名字，只看渲染图——已踩坑，见文末）。
3. **最省事的路线**：狐狸直接用 CC0 现成资产；人用「Q 版小孩/冒险者基础体」+
   自己加头盔和围巾。理由见「定制件」一节。
4. 本地 `assets3d/` 里已有一套程序化替身（见文末「项目现状」），可先对齐比例。

---

## 一、狐狸（匹配度高，建议直接用）

| 模型 | 平台 | 授权 | 面数 | 骨骼/动画 | 备注 |
|---|---|---|---|---|---|
| [Fox — Quaternius](https://poly.pizza/m/Bc97C66HKi) | Poly Pizza | **CC0** | 低模 | 带动画 | 橙色四足、白胸白尾尖、深色腿。**与概念图狐狸最接近的低模**，已下载到本目录 `quaternius_fox_cc0.glb` |
| [Low poly fox by PixelMannen (Animated)](https://sketchfab.com/3d-models/low-poly-fox-by-pixelmannen-animated-371dea88d7e04a76af5763f2a36866bc) | Sketchfab | CC-BY | 576 三角面 | **已绑定 + 动画** | 极轻量，游戏首选；原作者 PixelMannen，绑定/动画 by tomkranis |
| [Rigged Cute low Poly Fox character](https://sketchfab.com/3d-models/rigged-cute-low-poly-fox-character-7291c7ac99f44a25acdf39ba37627aa8) | Sketchfab | CC-BY | 17.8k | **已绑定** | 大头 Q 版，萌系，接近概念图的「宠物感」 |
| [FuzzleFox \| Cute Stylized Cartoon Fox](https://sketchfab.com/3d-models/fuzzlefox-cute-stylized-cartoon-fox-character-884fce565b49454db163352f92e48130) | Sketchfab | CC-BY | 28.2k | 未绑定 | 橙身白肚、大眼，成品感强，适合做近景主角 |
| [3D stylized fox game character](https://sketchfab.com/3d-models/3d-stylized-fox-game-character-4c24fb107c4545eeb49e3dd8b4924d12) | Sketchfab | CC-BY | 34.1k | 未绑定 | 大耳白肚橙狐，造型讨喜，Blender/Cycles 制作 |
| [Stylized Fox Family（Animated）](https://www.deviantart.com/kilutica3d/art/Stylized-Fox-Family-%5BAnimated-Game-Assets%5D-1270672703) | DeviantArt | 作者页确认 | — | **成体系带动画** | 公/母/幼狐三只一套，风格统一，适合做「狐狸一家」 |

**狐狸推荐**：要**能直接进引擎跑动画**选 Quaternius Fox（CC0）或 PixelMannen Fox；
要**近景好看**选 FuzzleFox / ameeerr 的 stylized fox，但需自行绑定。

---

## 二、人（宇航员小孩）

### 2.1 最接近「Q 版宇航员」的

| 模型 | 平台 | 授权 | 面数 | 骨骼 | 备注 |
|---|---|---|---|---|---|
| [Chibi Astronaut character concept](https://sketchfab.com/3d-models/chibi-astronaut-character-concept-eaaad633ea4041eca0270a32e3443ff4) | Sketchfab | CC-BY | 3.9k | 否 | **唯一真正的「Q 版小孩 + 宇航服 + 泡泡头盔」**。但作者定位是女孩（紫发可见），需去掉头发/改脸 |
| [Stylized Astronaut – Game-Ready](https://sketchfab.com/3d-models/stylized-astronaut-game-ready-27056600c2ac49f2827c4c5fc0a82940) | Sketchfab | Sketchfab Free Standard | 4.4k | **已绑定** | 写实比例宇航员（非 Q 版），**rigged + 游戏就绪 + PBR + 面罩高光贴图**，工程上最省事 |
| [Astronaut Chibi 3D-Model Rigged](https://www.deviantart.com/kilutica3d/art/Astronaut-Chibi-3D-Model-Rigged-951035712) | DeviantArt | 作者页确认 | — | **已绑定** | 4K 贴图 Q 版宇航员，可动画/摆拍 |

### 2.2 免费站（Poly Pizza）里可用的宇航员

| 模型 | 授权 | 说明 |
|---|---|---|
| [Rigged Astronaut — J-Toastie](https://poly.pizza/m/0oBRDJ9Zl9) | CC-BY 3.0 | **经典白色宇航员、已绑定、T-pose**，最稳妥的基础体 |
| [Astronaut — Poly by Google](https://poly.pizza/m/dLHpzNdygsg) | CC-BY 3.0 | 白服黑面罩经典造型 |
| [Astronaut — PW Wu](https://poly.pizza/m/erlAEWfFKH3) | CC-BY 3.0 | 白蓝配色小宇航员，偏可爱 |
| [Astronaut — Polygonal Mind](https://poly.pizza/m/4orkFqR9c9) | **CC0** | 高饱和风格化，配色活泼 |
| [Astronaut — Polygonal Mind](https://poly.pizza/m/UeBrldDxE9) | **CC0** | 同上，另一套配色 |

### 2.3 若「围巾+背包」是重点，用冒险者基础体更好

概念图里小孩的**金色围巾 + 背包**气质更接近「冒险者」而非纯宇航员。
[KayKit – Character Pack: Adventurers](https://kaylousberg.itch.io/kaykit-adventurers)
（**CC0，5 个角色，已绑定 + 动画，可商用免署名**）与
[Kenney Blocky Characters](https://kenney.nl/assets/blocky-characters)
（**CC0，18 角色 / 27 动画，已绑定**）是最省事的「人」基础体：
拿一个小孩体型 → 加圆头盔 → 加围巾，比找现成宇航员更贴近原图。

---

## 三、可直接用的候选图（本目录）

- `01_免费站候选_宇航员与男孩.png` — Poly Pizza 15 个候选横向对比（含作者/授权）
- `02_Sketchfab候选_宇航员与狐狸.png` — Sketchfab 6 个候选横向对比
- `03_Quaternius狐狸_CC0_预览.png` — 已下载狐狸的渲染预览
- `quaternius_fox_cc0.glb` — **可直接导入 Unity/UE/Blender 的 CC0 狐狸**

---

## 四、需要自己补的「定制件」

这几个特征在现成资产里基本找不到，必须自己加：

1. **金色围巾**（带飘带）——参照图里的识别性最强元素
2. **圆头盔 + 通体黑面罩**（不露脸，只有轮廓反光）
3. **背包 + 侧挂发光条**（`PackGlow`）
4. **狐狸的鞍具/背带 + 橙色鞍垫**
5. 小孩的**头身比约 1:1.6**（比常见 Q 版更「矮胖」）

好消息：本地 Blender 文件里这 5 项**都已经有对应物件**了，只是形还在白模阶段。

---

## 五、项目现状（重要）

本机已有：`StarWalkerVision/assets3d/starjourney_heroes.blend`

场景内 38 个对象，**两个角色都已搭好结构**：

- **宇航员**：`Astronaut_ROOT` / `Body` / `Helmet` / `Visor` / `VisorRim` /
  `Pack` / `PackGlow` / `ScarfCollar` / `ScarfTail` / `Arm_L·R` / `Glove_L·R` /
  `Leg_L·R` / `Boot_L·R`
- **狐狸**：`Fox_ROOT` / `Body.001` / `Chest` / `Head` / `Muzzle` / `Nose` /
  `Ear_L·R` / `Eye_L·R` / `Tail` / `TailTip` / `Paw_-1_-1` 等四爪

目前是**程序化白模/色块**，无骨骼（`armatures` 为空）、无动画（`actions` 为空）。
另有导出的 `fox.glb`、`astronaut.glb`。

**因此建议**：不要从零换模型，而是二选一
- **A（快）**：把上面的 CC0/CC-BY 狐狸直接替换现有 `Fox_ROOT`，人沿用现有结构细化；
- **B（稳）**：人换成 KayKit/Kenney 的 CC0 绑定基础体，狐狸换 Quaternius CC0，
  再统一套自己做的材质，保证一条管线出动画。

---

## 六、避坑记录

- ⚠️ **Poly Pizza 上 Quaternius 那个名字叫 “Astronaut” 的模型
  （`poly.pizza/m/0D54W8yfrA`）其实是「青蛙宇航员」**，青蛙头 + 宇航服身体，
  不是人。它的标签里写着 `Amphibian`/`Frog`。**光看名字会踩坑**，所以本清单
  的候选都逐一看过渲染图。
- ⚠️ Poly Pizza 搜 “astronaut” 的结果里混着大量 `Spaceship` / `Rocket` /
  `Satellite`，且部分 “Astronaut” 实为外星人/机器人（`zbtPq4dOJL`、
  `OgeSH89Nmx`、`WVliq38EJz`），选型时务必点开看图。
- ⚠️ Sketchfab 的 **“Free Standard”** 与 **CC-BY** 不同：CC-BY 只需署名；
  Free Standard 允许用于项目但不允许把模型本身再分发。商用前请回到模型页
  确认授权。
- ⚠️ 概念图本身是 AI 生成的美术方向稿，**不要试图找「同一个模型」**；
  正确做法是找风格接近的资产 + 自己补定制件。

## 七、还想要更多，可以这样搜

- Sketchfab：`chibi astronaut`、`stylized astronaut rigged`、`cute fox low poly animated`
- Poly Pizza：`astronaut`、`fox`、`boy`（免登录、直接下 GLB）
- Kenney / KayKit / Quaternius：CC0 游戏角色全套，适合做基础体
- 中文站：CG模型网 `cgmodel.com`、摩尔网 `cgmol.com`（注意商用授权需另购）

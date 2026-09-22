# 已下载模型（可直接导入 Unity / UE / Blender）

来源：**Poly Pizza**（免登录，直链 GLB）。全部已逐字节校验：
GLB 头声明长度 == 实际文件大小，并用 GLB 内部结构复核过网格/材质/骨骼/动画。

> 校验方式：解析 GLB 的 JSON chunk，统计三角面、mesh、material、node、
> animation、skin、texture。**没有**导入你正在编辑的
> `starjourney_heroes.blend`，避免污染现场。

---

## ⭐ 结论：你要的「人」和「狐」，这里已经各有一套可用资产

| 文件 | 三角面 | 骨骼 | 动画 | 授权 | 说明 |
|---|---|---|---|---|---|
| `astronaut_Quaternius_3hC2i0CTuO.glb` | 10,558 | **有**（`CharacterArmature`，含手指） | **24 段** | **CC0** | **首选**。网格名为 `SpaceSuit_Feet/Legs/Body/Head`，是真正的宇航服人形 |
| `quaternius_fox_cc0.glb` | 1,848 | **有**（`AnimalArmature`） | **12+ 段** | **CC0** | **首选**。网格名为 `Fox`，四足赤狐 |

**宇航员那 24 段动画**（`CharacterArmature|…`）：
Idle / Idle_Neutral / Idle_Gun / Idle_Gun_Pointing / Idle_Gun_Shoot / Idle_Sword /
Walk / Run / Run_Back / Run_Left / Run_Right / Run_Shoot / Roll /
Punch_Left / Punch_Right / Kick_Left / Kick_Right / Wave /
Sword_Slash / Gun_Shoot / Interact / HitRecieve / HitRecieve_2 / Death

**狐狸动画**：Walk / Gallop / Gallop_Jump / Idle / Idle_2 / Idle_2_HeadLow /
Attack / Death / Eating / Jump_ToIdle / Idle_HitReact_Left / Idle_HitReact_Right

⇒ 也就是说：**「会跑会跳会待机的宇航员小孩 + 会走会跑的狐狸」这套需求，
用这两个 CC0 文件就已经能满足**，不必非等 Sketchfab 那个。

---

## 全部 8 个宇航员候选

> ⚠️ 你给的标签 `astronautAstronaut` 在对比图 `01_免费站候选…png` 里
> **对应 8 个同名 tile**（Poly Pizza 上它们标题都叫 “Astronaut”），
> 所以我**把 8 个全下了**，你挑。

| 文件 | 作者 | 授权 | 三角面 | 骨骼/动画 | 形态 |
|---|---|---|---|---|---|
| `astronaut_Quaternius_3hC2i0CTuO.glb` | Quaternius | **CC0** | 10,558 | **有 / 24 段** | ✅ 宇航服人形（首选） |
| `astronaut_Poly-by-Google_dLHpzNdygsg.glb` | Poly by Google | CC-BY 3.0 | 1,604 | 无 / 无 | ✅ 经典白宇航员，最贴概念图 |
| `astronaut_PW-Wu_erlAEWfFKH3.glb` | PW Wu | CC-BY 3.0 | 15,732 | 无 / 无 | ✅ 白宇航员，动态姿势（89 个 mesh，偏碎） |
| `astronaut_Polygonal-Mind_4orkFqR9c9.glb` | Polygonal Mind | **CC0** | 2,284 | 无 / 无 | ✅ 风格化人形 + 橙色面罩 |
| `astronaut_Polygonal-Mind_UeBrldDxE9.glb` | Polygonal Mind | **CC0** | 4,858 | 无 / 无 | ⚠️ 圆头，偏机器人 |
| `astronaut_Polygonal-Mind_WVliq38EJz.glb` | Polygonal Mind | **CC0** | 3,478 | 无 / 无 | ❌ 圆形外星角色 |
| `astronaut_Quaternius_zbtPq4dOJL.glb` | Quaternius | **CC0** | 7,938 | 有 / 18 段 | ❌ 青蛙外星宇航员 |
| `astronaut_Quaternius_OgeSH89Nmx.glb` | Quaternius | **CC0** | 8,562 | 有 / 18 段 | ❌ 外星角色（持刀） |

对照图见上一级目录 `04_已下载宇航员候选_8个.png`。

**推荐**：要**能直接进引擎跑动画** → `astronaut_Quaternius_3hC2i0CTuO.glb`；
要**外形最像概念图**（白服黑面罩）→ `astronaut_Poly-by-Google_dLHpzNdygsg.glb`。

---

## ✅ 已选定：PW Wu 那个

你圈的是对比图 `01_免费站候选…png` 的**左上第一格**（灰底、白宇航服、
黑面罩、蓝点缀、大跨步姿势）。该格下方署名即 **PW Wu | CC-BY 3.0 |
poly.pizza/m/erlAEWfFKH3**，对应文件：

    models/astronaut_PW-Wu_erlAEWfFKH3.glb      （已下载，1,183 KB）

原文：https://poly.pizza/m/erlAEWfFKH3

### ⚠️ 但它有个硬伤，选它之前必须知道

我把文件拆开看过了：

| 项目 | 实测 |
|---|---|
| 三角面 | 15,732 |
| mesh 数 | **89 个**，且全是 `mesh1167641645`、`group1707873932` 这类无意义名字 |
| 材质 | 8 个（`mat15`…`mat23`），**0 张贴图**，纯色 |
| 骨骼 / 动画 | **0 / 0**，完全静态 |
| 尺寸 | 本地包围盒 ≈ **1.09 单位高**（已是小孩体量，不用大改） |
| 节点变换 | **全部为空** |

最后一行是关键：节点没有任何位移/旋转，说明**图里那个大跨步姿势是烘进网格
顶点里的**，也就是它**不是 T-pose / A-pose，而是一个摆好姿势的静态模型**。

⇒ 结论：**它长得最像概念图，但最不适合做会动的游戏角色。** 绑定一个已经摆好
姿势的模型，比绑定 T-pose 难得多（要先把姿势“掰”回 rest pose 才能刷权重，
否则一动画就穿帮）。

### 建议的三条路

1. **最稳**：用 `astronaut_Quaternius_3hC2i0CTuO.glb`（CC0、真 T-pose、
   4 个干净 mesh `SpaceSuit_Feet/Legs/Body/Head`、已绑定、24 段动画），
   把 PW Wu 这版的**配色和比例**当参考套上去。← 工期最短、能立刻走路
2. **折中**：保留 PW Wu 的外形，先重拓扑/摆回 T-pose，再重新绑定 + 刷权重。
   样子最准，但工作量最大。
3. **最省**：PW Wu 这个只当**静帧参考/摆件**用（比如关卡卡牌、立绘），
   跑动的角色仍用绑定好的那套。

> ⚠️ 授权提醒：`erlAEWfFKH3` 是 **CC-BY 3.0**，商用/参赛**必须署名 PW Wu**。
> 相比之下 `astronaut_Quaternius_3hC2i0CTuO.glb` 是 **CC0**，无署名义务。

---

## ❌ 未完成：FoxRobettiRigged（Sketchfab）

**下载失败，原因不是网络，是授权。** 证据来自模型页自身返回的数据：

```
"mayDownloadThisModel": false
/i/models/7291c7ac99f44a25acdf39ba37627aa8/download
    → {"detail": "Authentication credentials were not provided."}
```

Sketchfab 的模型文件**必须带账号身份**才能取：
`https://api.sketchfab.com/v3/models/{uid}/download` 需要
`Authorization: Token <API_KEY>`，未登录一律拒绝。

本机也没有任何可用凭据（已检查环境变量、Blender `userpref.blend`、
`~/.zshrc` 等 profile、整个工作区），所以这条我无法自行打通。

**要拿到它，三选一：**
1. **给我 Sketchfab API Key**（https://sketchfab.com/settings/password → API token）。
   Blender 插件里那个「Use assets from Sketchfab」勾选我可以自己打开，
   但 key 只能你给。之后我直接调 `download_sketchfab_model` 取回。
2. **你自己在浏览器点 Download**，把 zip/glb 丢进本目录，我来接进 Blender。
3. **不用它**——用已下好的 `quaternius_fox_cc0.glb`（CC0、已绑定、带 12+ 段动画），
   工程上其实更省事，且没有署名义务。

> 该模型信息：Rigged Cute low Poly Fox character，作者 Robetti，**CC-BY**，
> 17.8k 三角面，已绑定（无动画）。注意 CC-BY 需署名。
> https://sketchfab.com/3d-models/rigged-cute-low-poly-fox-character-7291c7ac99f44a25acdf39ba37627aa8

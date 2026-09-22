# 从 Blender 建模到 UE 运行 · 实现方案

> 依据《[向星而行 · UE 实现架构与设计](向星而行_UE实现架构与设计.md)》。设计文档已经定了**要什么**（§5 资产清单、§5.1 色板、§6 动画表）和**先灰盒再美术**的顺序；本文补的是中间那条管线：**Blender 里的模型产物，如何变成 UE 里真正跑起来、能被玩法状态驱动的角色与场景**。
>
> 方案基于仓库当前真实状态（已实测，见 §1），不是凭空设计。

---

## 1. 现状盘点（实测）

| 项 | 实测结果 | 结论 |
|---|---|---|
| `Content/Models/astronaut.glb` | 16 个独立网格物件；包围盒 `1.84 × 1.28 × 2.24 m`；脚底 `z = -0.18`；面朝 **+X** | 需**合并、重设原点、修正朝向、缩放** |
| `Content/Models/fox.glb` | 15 个独立网格物件；包围盒 `2.25 × 0.86 × 1.60 m`；脚底 `z = -0.14`；面朝 **+X** | 同上 |
| `Content/Models/starjourney_heroes.blend` | Blender 5.1.2 源工程 | 保留为**源真值**，继续在此迭代 |
| `AStarRunnerPawn` | `Capsule(40, 90)` → 高 180 cm；只有 `Capsule + VisualRoot` | **没有 `USkeletalMeshComponent`**，角色表现目前是占位 |
| 骨骼 / 动画 / AnimBP | 全部不存在 | 设计文档 §6 的跑步、换道、蹲下、抬腿、开合跳、狐狸待机**全部缺** |
| 工具链 | Blender 5.1.2（本机可脚本化）、UE 5.8 + VS 2022（你的 Windows） | Blender 侧可自动化；UE 侧需你在 Windows 执行 |

**所以这条管线要解决的不是"再建几个模型"，而是四件事**：把拼装件变成可绑骨网格 → 定死单位/原点/朝向约定 → 建立骨架与动画 → 把动画接到已有的玩法状态机上。

---

## 2. 必须先冻结的四个约定

这一节是全文最关键的部分。**约定错了，后面所有资产都要返工**。

### 2.1 单位与缩放

| | Blender | UE |
|---|---|---|
| 单位 | 1 单位 = 1 米 | 1 uu = 1 厘米 |
| 换算 | **× 100** | — |

**做法**：在 FBX 导出时设 `global_scale = 100`，让导出文件本身就是厘米制，UE 导入缩放保持 1。这比"导出 1、导入时填 100"更不容易漏，且 FBX 自描述。

**角色目标尺寸**（与玩法对齐，不由美术随意定）：

| 角色 | 目标高度 | 依据 |
|---|---|---|
| 宇航员 | **180 cm** | 等于 Pawn 胶囊总高（`InitCapsuleSize(40, 90)`），脚底贴胶囊底 |
| 狐狸 | **55 cm** | 设计文档「小伙伴」比例，明显小于主角 |
| 云鲸 | 长约 **800 cm** | 远景巨兽，配合 `build_scene.py` 的道路尺度 |

> 当前宇航员 224 cm，**必须缩到 180 cm**。要么改模型缩放，要么改胶囊；方案选择改模型——胶囊尺寸同时影响碰撞与玩法调参，不该为美术让路。

### 2.2 原点与朝向

两条都是 UE 角色的硬性要求，当前**都不满足**：

1. **原点必须在双脚落点、Z = 0**。现在脚底在 `z = -0.18`（宇航员）/ `-0.14`（狐狸），意味着原点在脚踝上方。不修的话模型会**陷进地面**。
2. **朝向：Blender 面向 -Y 导出后 UE 面向 +X**。这是 Blender→UE 的标准映射（FBX 导出保持 `Forward = -Z, Up = Y`）。当前模型面朝 **+X**，等于**在 UE 里会侧身 90° 跑**。修法：绕 Z 轴旋转 **-90°**，把 +X 转到 -Y。

**顺带定死左右**：面朝 -Y、Z 朝上时，角色的**左手在 +X**（`left = up × forward = Z × (-Y) = +X`）。这一点必须与设计文档「左右按玩家身体定义，不能因相机镜像反过来」对齐 —— 所以 §7 的验收里有一条是**真人抬左腿，必须抬起角色的左腿**。

### 2.3 命名规范

| 类别 | 规范 | 示例 |
|---|---|---|
| 骨骼 | 小写 + 下划线，左右后缀 `_l` / `_r` | `pelvis`、`thigh_l`、`tail_2` |
| 动画 | `A_<角色>_<动作>[_<方向>]`，循环加 `_Loop` | `A_Hero_Run_Loop`、`A_Hero_Jack_Start` |
| 骨骼网格 | `SK_<角色>` | `SK_Hero`、`SK_Fox`、`SK_Whale` |
| 骨架 | `SKEL_<角色>` | `SKEL_Hero` |
| AnimBP | `ABP_<角色>` | `ABP_Hero` |
| 静态件 | `SM_<类别>_<名称>` | `SM_Station_Lamp`、`SM_Prop_Mushroom` |
| 材质 | `M_<角色>_<部位>` / `MI_<...>` | `M_Hero_Suit` |

### 2.4 导出格式（给结论）

| 资产 | 格式 | 理由 |
|---|---|---|
| **带骨骼的角色**（宇航员/狐狸/云鲸） | **FBX**，`global_scale=100`、`Forward=-Z`、`Up=Y`、勾选 `Armature` + `Bake Animation` | FBX 的多段动画（take）在 UE 里按**每段一个 AnimSequence** 导入，是最成熟、最少意外的路径 |
| **静态件**（树/石/蘑菇/机关/云桥/巨行星/群山） | **GLB**（`export_yup=True`） | 单件无骨骼，glTF 更小、材质自包含；朝向错了肉眼立刻可见，好修 |

> 仓库现在把 `.glb` 放在 `Content/Models/`。方案建议改为：**源真值与导出件放 `Content` 之外**（见 §6.1），避免 UE 把非资产文件混在内容目录里。

---

## 3. 资产分类与规格表

| 资产 | 类型 | 骨架 | 动画 | 来源 |
|---|---|---|---|---|
| 宇航员（主角） | 骨骼 | 有（约 18 骨） | 跑 / 待机 / 换道左右 / 蹲三态 / 抬腿左右 / 开合跳三段 | 现有 `astronaut.glb` 升级 |
| 拾光狐狸 | 骨骼 | 有（约 12 骨） | 跑 / 待机 / 尾巴摆动 | 现有 `fox.glb` 升级 |
| 云鲸 | 骨骼（少量） | 有（约 6 骨） | 6–8 秒缓慢浮动 | 新建（设计文档 §5：低模 + 尾巴/鳍少量骨骼） |
| 邮站 / 信箱 | 静态 | — | — | 新建 |
| 风车 | 静态 + 旋转件 | — | 转速用 Timeline（设计文档 §6） | 新建 |
| 信封 / 纸飞机 | 静态 | — | 飞行走 Spline | 新建 |
| 路灯 / 花台 | 静态 | — | 点位驱动（Timeline） | 新建，与 `AStarStation` 配合 |
| 树 / 石块 / 蘑菇 | 静态 | — | — | 新建，替换 `LP_sci_fi_island` 占位 |
| 云桥 / 云岛 | 静态 | — | — | 新建 |
| 巨行星 / 三层群山 | 静态（Unlit / Masked） | — | 视差由相机移动产生 | 替换 `build_scene.py` 里的球/锥占位 |
| 道路与分隔线 | 静态 | — | — | 已有 `01_Road` 生成逻辑，可保留 |

**优先级**（对齐设计文档 §8「先做一个能证明画面质量的短场景」）：**宇航员 → 六动作 → 狐狸 → 路灯机关 → 云鲸 → 其余场景件**。

---

## 4. Blender 侧实现（可脚本化、可入 Git）

### 4.1 前置处理：从「拼装件」到「可绑骨网格」

当前两个角色是**十几个独立网格物件**拼出来的（这是灰盒阶段的合理形态）。绑骨前必须：

1. **合并**为一个网格（`object.join`）。多网格也能各自蒙皮到同一骨架，但 UE 侧一个 `SkeletalMesh` 最省事，且避免导出时材质槽错乱。
2. **重设原点**到双脚落点（Z = 0）。
3. **旋转 -90°**（+X → -Y），并 `apply rotation`（否则导出后 UE 里仍有 90° 残留）。
4. **缩放到目标高度**（宇航员 ×(180/224)，狐狸按 55 cm 目标）。
5. 合并后按材质**分材质槽**，保留原有 8 个色板材质（`Suit/Visor/Pack/Scarf/Fox/FoxCream/Black/Gold`）。

### 4.2 骨架规格

**宇航员（`SKEL_Hero`，约 18 骨，不做面部）**

```
root
└─ pelvis
   ├─ spine ─ chest ─ neck ─ head
   │           ├─ shoulder_l ─ upperarm_l ─ lowerarm_l ─ hand_l
   │           └─ shoulder_r ─ upperarm_r ─ lowerarm_r ─ hand_r
   ├─ thigh_l ─ shin_l ─ foot_l ─ toe_l
   └─ thigh_r ─ shin_r ─ foot_r ─ toe_r
```

**狐狸（`SKEL_Fox`，约 12 骨）**

```
root ─ pelvis ─ spine ─ chest ─ neck ─ head ─ ear_l / ear_r
                          └─ tail_1 ─ tail_2 ─ tail_3
       frontleg_l/r、hindleg_l/r（各 2 节）
```

**云鲸（`SKEL_Whale`，约 6 骨）**：`root`、`body`、`tail_1`、`tail_2`、`fin_l`、`fin_r`。

> 骨架**从简**：设计文档要求的是"圆润低模 + 少量骨骼"，不是写实绑定。骨骼越少，权重越好做、动画越好调。

### 4.3 蒙皮

- 用**自动权重**（`parent_set(type='ARMATURE_AUTO')`）打底。
- 手工修正的重点：肩、髋、颈（拼装件的球体在这些位置容易互相穿插）；开合跳的双臂上举、蹲下的髋膝，是权重问题最容易暴露的两个动作。
- **保留 `Suit` 等纯色材质**，不做贴图 —— 与设计文档「低细节轮廓」一致，也避免 UV 工作量。

### 4.4 动画清单（对齐设计文档 §6 的时长，30 fps）

设计文档 §6 给的时长是**视觉起调值**，这里折算成帧：

| 动画 | 类型 | 帧数 | 对应文档条目 |
|---|---|---|---|
| `A_Hero_Idle_Loop` | 循环 | 30（1.0 s） | 待机/准备 |
| `A_Hero_Run_Loop` | 循环 | 16（0.53 s） | 跑步：轻快小步、起伏小 |
| `A_Hero_Lane_Left` | 单次 | 11（0.37 s） | 换道 0.3–0.45 s，先离地再横移 |
| `A_Hero_Lane_Right` | 单次 | 11 | 同上 |
| `A_Hero_Squat_In` | 单次 | 5（0.17 s） | 蹲下**约 0.15 s 混入** |
| `A_Hero_Squat_Loop` | 循环 | 20 | 持续俯身（不自动站起） |
| `A_Hero_Squat_Out` | 单次 | 5 | 真实站立后混出 |
| `A_Hero_LegLift_Left_Up` / `_Down` | 单次 ×2 | 各 6 | 左右跨步：**两段短动画** |
| `A_Hero_LegLift_Right_Up` / `_Down` | 单次 ×2 | 各 6 | 同上 |
| `A_Hero_Jack_Start` | 单次 | 8 | 开合跳 **Start / Hold / End 三段** |
| `A_Hero_Jack_Hold` | 循环 | 6 | 打开后保持（等 Complete） |
| `A_Hero_Jack_End` | 单次 | 8 | 收回 |
| `A_Fox_Idle_Loop` | 循环 | 40 | 狐狸待机 + 耳朵轻动 |
| `A_Fox_Run_Loop` | 循环 | 16 | 狐狸跑步、尾巴错相摆动 |
| `A_Whale_Float_Loop` | 循环 | 200（6.7 s） | 云鲸 **6–8 秒缓慢浮动**，尾部轻摆 |

**共同要求**：
- **全部 in-place，不做 root motion**。位移由 C++（`UpdateForward`/`UpdateLane`）驱动；设计文档明确要求「In-place 跑步循环」。
- 循环动画**首尾帧姿态一致**，否则会出现跳帧。
- 关键动作的"接触点"要对齐玩法阈值：例如抬腿动画的抬脚峰值应落在 `HandleAction` 发出 Begin 后的前几帧，避免"游戏已经跨过障碍、动画还在抬腿"。

### 4.5 脚本化与自检

新增 Blender 脚本（`bpy`，可入 Git、可重复执行）：

```
art/blender/build_hero.py     # 合并/重设原点/朝向/缩放 → 骨架 → 自动权重 → 导出 FBX
art/blender/build_fox.py
art/blender/build_whale.py
art/blender/lib_pipeline.py   # 共用：pipeline_prepare() / add_armature() / export_fbx()
```

每个脚本末尾**自检断言**（失败即报错，不产出文件）：

- 合并后网格数 == 1
- 脚底 `abs(min_z) < 1e-4`（原点在脚）
- 朝向：面罩/鼻子的世界 X < 0（已转向 -Y）
- 高度 == 目标值 ±1 cm
- 骨骼数 == 预期值、骨骼命名全部符合 §2.3
- 动画段数 == 预期值、每段帧数符合 §4.4
- 导出文件存在且体积在合理区间（防"导出空文件"）

---

## 5. UE 侧实现

### 5.1 资产目录规范

```
Content/StarJourney/Characters/
  Hero/    SK_Hero, SKEL_Hero, A_Hero_*, ABP_Hero, PHY_Hero
  Fox/     SK_Fox, SKEL_Fox, A_Fox_*, ABP_Fox
  Whale/   SK_Whale, SKEL_Whale, A_Whale_Float_Loop
Content/StarJourney/Props/
  Stations/  SM_Station_*
  Nature/    SM_Tree_*, SM_Rock_*, SM_Mushroom_*
  Sky/       SM_Planet, SM_Ridge_*
```

导入方式：**用脚本导入**（新增 `Content/Python/import_art.py`，由 `Manage-StarJourney.ps1` 新动作 `ImportArt` 调用），而不是手工拖拽 —— 手工导入无法复现，也没有记录。

导入关键设置：

| 设置 | 值 | 原因 |
|---|---|---|
| Skeletal Mesh | 是 | 角色 |
| Import Uniform Scale | 1.0 | 缩放已在导出时烘焙成厘米 |
| Import Animations | 是 | 每段 take → 一个 AnimSequence |
| Create Physics Asset | 是 | 为后续布娃娃/受击留口，但**运行时不用它做碰撞**（见 §5.7） |
| Import Materials | 是 | Blender Principled → UE 材质 |

### 5.2 材质映射

Blender 的 `Principled BSDF` 会被转成 UE 材质：Base Color → Base Color，Roughness → Roughness，Emission → Emissive Color。现有 8 个色板材质（`#E0E8E6` 宇航服、`#1B354B` 面罩、`#EFAF66` 围巾、`#D89057` 狐狸、`#FFD18C` 金色自发光）都能直接过。

后续如需统一，把这些生成的材质**重父级到 `M_StarMaster`**（一个含 BaseColor/Roughness/Emissive 参数的母材质），让美术调参不改模型。

### 5.3 骨骼网格接入 Pawn

`AStarRunnerPawn` 现在只有 `Capsule + VisualRoot`。改造：

- 新增 `USkeletalMeshComponent* Mesh`，`SetupAttachment(Capsule)`，与 `VisualRoot` **同位置**（保留 `VisualRoot` 作为降级占位：没配骨骼网格时仍用拼装件，便于在美术未就位时继续开发）。
- **`ApplyVisualOffset()` 的偏移继续生效**：跳跃弧线（Z 上）与蹲下俯身（Z 下）仍作用在视觉根上 —— 换道已经改为移动 Pawn 本体（§3 已实现），骨骼网格挂在胶囊上自然跟随。
- 关闭骨骼网格的碰撞（`SetCollisionEnabled(NoCollision)`），碰撞仍由胶囊负责。
- `Mesh` 设为 `AnimMode::AnimationBlueprint`，AnimBP 类用 `UPROPERTY(EditDefaultsOnly) TSubclassOf<UAnimInstance>` 暴露，便于在编辑器里指。

### 5.4 AnimBP 状态机 vs Montage 的分工

这是本方案唯一需要"设计判断"的地方，给结论：

| 内容 | 载体 | 理由 |
|---|---|---|
| 待机 / 跑步 | AnimBP **状态机**（`Idle` ⇄ `Run`） | 长驻状态，由 `IsRunning()` 拉取即可 |
| 蹲下三态 | AnimBP **状态机**（`SquatIn` → `SquatLoop` → `SquatOut`） | 与 `SquatAlpha`（0→1→0）一一对应，是连续量 |
| 换道左右、抬腿左右、开合跳 | **AnimMontage**，由 C++ 在 `Begin` 时播放 | 这些是**离散、有时限**的一次性动作；状态机追踪"这一段播完没有"很容易出现竞态，Montage 由引擎负责播放与结束 |

**契约（冻结，C++ 与 AnimBP 双方按此实现）**：

```cpp
UENUM(BlueprintType)
enum class EStarAnimState : uint8 { Idle, Run, Squat, Jack, LaneLeft, LaneRight, LegLeft, LegRight };

UFUNCTION(BlueprintPure) EStarAnimState GetAnimState() const;  // 状态机用
UFUNCTION(BlueprintPure) float GetSquatAlpha() const;          // 0..1，蹲下混合
UFUNCTION(BlueprintPure) bool  IsRunning() const;              // 已有

// 一次性动作的资源引用，在编辑器里指派（C++ 不硬编码资产路径）
UPROPERTY(EditDefaultsOnly, Category="Star|Anim") TObjectPtr<UAnimMontage> JackMontage;
UPROPERTY(EditDefaultsOnly, Category="Star|Anim") TObjectPtr<UAnimMontage> LaneLeftMontage;
UPROPERTY(EditDefaultsOnly, Category="Star|Anim") TObjectPtr<UAnimMontage> LaneRightMontage;
UPROPERTY(EditDefaultsOnly, Category="Star|Anim") TObjectPtr<UAnimMontage> LegLeftMontage;
UPROPERTY(EditDefaultsOnly, Category="Star|Anim") TObjectPtr<UAnimMontage> LegRightMontage;
UPROPERTY(EditDefaultsOnly, Category="Star|Anim") TObjectPtr<UAnimMontage> SquatMontage; // 可选
```

`BeginAction()` 里在改运动状态的同时播放对应 Montage；`CompleteAction()` 时若 Montage 仍在播则停掉或让其自然收尾（按动作决定：开合跳要等 Hold → End）。

> **不把资产路径写进 C++**：Montage 用 `EditDefaultsOnly` 由编辑器指派。这样换美术不用改代码，也避免 C++ 依赖具体资产名。

### 5.5 狐狸与云鲸

- **狐狸**：不是 Pawn，是跟随 Actor。用一个 `AStarCompanionFox : AActor`（`USkeletalMeshComponent` + `ABP_Fox`），位置用弹簧插值跟随 Pawn 的固定偏移（设计文档 §6：`插值跟随固定偏移`）。它的动画状态只有 `Idle`/`Run`（按 Pawn 是否在跑切换），尾巴摆动包含在待机/跑步循环里。
- **云鲸**：背景 Actor，`AWhaleDrifter`，骨骼网格 + `A_Whale_Float_Loop` 单曲循环，沿 Spline 缓慢飞行（设计文档 §6）。

### 5.6 场景静态件的接入

`build_scene.py` 目前用 `/Engine/BasicShapes`（Cube/Sphere/Cone）和 `LP_sci_fi_island` 素材包当占位。美术件就位后，**不改生成逻辑，只换映射表**：

```python
# build_scene.py 里新增/替换的映射
ART = {
    'Tree':     '/Game/StarJourney/Props/Nature/SM_Tree_A',
    'Rock':     '/Game/StarJourney/Props/Nature/SM_Rock_A',
    'Mushroom': '/Game/StarJourney/Props/Nature/SM_Mushroom_A',
    'Lamp':     '/Game/StarJourney/Props/Stations/SM_Station_Lamp',
    'Planet':   '/Game/StarJourney/Props/Sky/SM_Planet',
    # ...
}
```

`mesh()` / `prop()` 已经是按名字取资产的统一入口，所以**替换是逐项、可回退的**：某一类美术没好，就继续用占位，不会阻塞其它项。

---

## 6. 版本控制与一键流水线

### 6.1 提交什么

| 内容 | 是否入库 | 说明 |
|---|---|---|
| `.blend` 源工程 | ✅ | 源真值，必须入库 |
| 导出的 `.fbx` / `.glb` | ✅ | 中间产物，但入库才能让"没装 Blender 的人"也能跑通导入 |
| Blender 脚本（`art/blender/*.py`） | ✅ | 让资产**可重建**，而不是只能手工改 |
| UE 导入脚本（`Content/Python/import_art.py`） | ✅ | 同上 |
| `.uasset`（骨骼网格/动画/AnimBP/材质） | ❌ | 二进制、体积大；由导入脚本生成。与现有 `Content/StarJourney/` 已被 `.gitignore` 排除的做法一致 |

**目录调整建议**：把源件与导出件从 `Content/Models/` 挪到 **`art/`（Content 之外）**。`Content/` 是 UE 的内容目录，非资产文件混在里面容易误操作；`art/` 语义更清楚：

```
art/
  blender/     build_hero.py / build_fox.py / build_whale.py / lib_pipeline.py
  source/      starjourney_heroes.blend
  export/      SK_Hero.fbx / SK_Fox.fbx / SM_*.glb
Content/Models/  ← 迁移后删除
```

### 6.2 一键流水线

在 `Manage-StarJourney.ps1` 增加两个动作，串成一条可重复的链路：

```powershell
# Windows 侧（Blender 可用时）
blender --background --python art/blender/build_hero.py     # 合并/绑骨/动画/导出 + 自检
.\Manage-StarJourney.ps1 -Action ImportArt                   # FBX/GLB → .uasset（脚本导入）
.\Manage-StarJourney.ps1 -Action PlayLevel                   # 生成玩法地图（已有）
.\Manage-StarJourney.ps1 -Action Validate                    # 自动播放校验（已有）
```

**关键点**：每一步都可独立重跑，且**自检失败就不产出文件**，避免半成品流进 UE。

---

## 7. 验证与验收（分阶段，可执行）

| 阶段 | 自动断言 | 人工目视 |
|---|---|---|
| 模型预处理 | 单网格、脚底 z=0、面朝 -Y、高度=目标 | 侧视/正视轮廓无穿插 |
| 骨架与蒙皮 | 骨骼数/命名符合 §4.2、§2.3 | 极限姿态（抬臂、深蹲）无撕裂 |
| 导出 | 文件存在、体积合理、动画段数正确 | Blender 内播放一遍 |
| UE 导入 | 资产存在、骨骼网格高 = 180 cm（用 `import_art.py` 断言） | 静态摆放比例正确 |
| 朝向 | 导入后**面罩朝 +X** | Play 时角色朝前跑而不是侧身 |
| 动画循环 | 首尾帧姿态差 < 阈值 | 跑步无跳帧 |
| 玩法联动 | `Begin` 时 Montage 开始播、`Complete` 时收尾 | **真人抬左腿 → 角色抬左腿**（左右不反，设计文档硬要求） |
| 相机 | — | 换道时镜头不左右摆（已实现，回归验证） |
| 蹲下 | `SquatAlpha` 与动画权重一致 | 蹲下保持到真实站起，不自动弹起 |

---

## 8. 里程碑与依赖

| # | 里程碑 | 内容 | 依赖 |
|---|---|---|---|
| **M1** | 约定固化 + 宇航员跑通 | §4.1 预处理 → 骨架 → 蒙皮 → 导出 → UE 导入 → 看到 180 cm 的宇航员站在地图上 | 无 |
| **M2** | 六动作 + AnimBP 接入 | §4.4 宇航员动画、§5.4 契约、`USkeletalMeshComponent` 接入 Pawn | M1 |
| **M3** | 狐狸 | 骨架/动画/`AStarCompanionFox` 跟随 | M1（可与 M2 并行） |
| **M4** | 云鲸 | 骨架/单曲循环/`AWhaleDrifter` | M1（可并行） |
| **M5** | 场景件替换占位 | §5.6 映射表逐项替换 | 可与 M2–M4 并行 |
| **M6** | 第二、三关内容 | 关卡数据文本驱动 + 主题 | M5 |

**M1 是最小可用闭环，风险也最集中**（单位/原点/朝向三个坑都在这一步暴露），建议先只做 M1 并在 Windows 上验收，再批量生产其余资产。

---

## 9. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| **单位/缩放错** | 角色大 100 倍或小 100 倍 | 导出 `global_scale=100` + 导入后断言高度=180 cm |
| **朝向错 90°** | UE 里侧身跑 | Blender 内转向 -Y + 导入后断言面罩朝 +X |
| **原点不在脚** | 角色陷地/悬空 | 预处理重设原点 + 断言 `min_z=0` |
| **拼装件合并后材质槽错乱** | 颜色错位 | 按材质分槽 + 目视 |
| 自动权重在肩/髋撕裂 | 动作难看 | 重点修肩髋颈；开合跳/深蹲专项检查 |
| FBX 多段动画被合成一段 | 动画无法单独调用 | 每段动画单独 action + 导出时 `Bake Animation`；导入后核对 AnimSequence 数量 |
| 重导入覆盖手工调整 | 编辑器里的改动丢失 | 手工调整只做在**母材质/AnimBP**层，不直接改导入资产 |
| 循环首尾不接 | 跑动跳帧 | 首尾帧姿态一致性断言 |
| **我无法编译 UE** | C++/AnimBP 改动只能静态审查 | 首次编译报错由你贴回，我逐个修 |
| `.uasset` 不入库 | 别人 clone 后没有资产 | 由 `ImportArt` 脚本重建（已有 `PlayLevel` 同思路） |

---

## 10. 分工：我能做的 / 需要你在 Windows 做的

| 工作 | 谁做 |
|---|---|
| §4 全部 Blender 工作（合并、骨架、权重、动画、导出脚本、自检） | **我**（本机 Blender 5.1.2 已接入，可直接建模并用脚本落地） |
| §5.3–§5.5 的 C++（`USkeletalMeshComponent` 接入、Montage 契约、狐狸/云鲸 Actor） | **我**编写，**你**编译验证 |
| §5.1–§5.2 导入脚本、§5.6 映射表、§6.2 PS1 动作 | **我**编写 |
| UE 内指派 Montage/AnimBP 资产、§5.4 状态机连线 | **你**（二进制资产，我写不了） |
| §7 全部验收（编译、Play、目视） | **你** |
| 动画的艺术质量迭代（好不好看） | 你给反馈，我在 Blender 侧改 |

---

## 11. 建议的第一步

先只做 **M1：宇航员**，一次把三个约定（单位、原点、朝向）验证到位，产出一个能在 UE 里站对位置、朝对方向、180 cm 高的骨骼网格。这一步走通，后面就是批量复制。

具体动作：

1. 我写 `art/blender/lib_pipeline.py` + `build_hero.py`（预处理 → 骨架 → 自动权重 → 导出 FBX + 自检）；
2. 我写 `Content/Python/import_art.py`（脚本导入 + 比例断言）与 PS1 的 `ImportArt` 动作；
3. 你在 Windows 跑一次，把结果（成功或报错）发我；
4. 通过后再做 M2 的六套动画。

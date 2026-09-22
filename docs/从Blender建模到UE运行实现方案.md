# 从 Blender 建模到 UE 运行 · 实现方案（v2）

> 依据《[向星而行 · UE 实现架构与设计](向星而行_UE实现架构与设计.md)》。
>
> **v2 变更说明**：v1 假设「给自制的拼装件绑骨 + 从零做 13 段动画」。经决策，角色改用 **CC0 现成绑定资产**，因此 v1 的骨架规格、蒙皮、逐段动画章节整体作废，替换为**资产归一化 + 片段映射 + 补做缺口片段**。全文数字均为**实测**（本地解析 GLB 得到），不是引用提交信息。

---

## 1. 现状与实测

### 1.1 自制资产（已入库）

| 项 | 实测 | 结论 |
|---|---|---|
| `Content/Models/astronaut.glb` | 16 个独立网格物件；`1.84 × 1.28 × 2.24 m`；脚底 `z = -0.18`；面朝 **+X** | 无骨骼；**尺寸/原点/朝向都不符合 UE 要求** |
| `Content/Models/fox.glb` | 15 个独立网格物件；`2.25 × 0.86 × 1.60 m`；脚底 `z = -0.14`；面朝 **+X** | 同上 |
| `Content/Models/starjourney_heroes.blend` | Blender 5.1.2 源工程 | 保留为源真值 |
| `AStarRunnerPawn` | `Capsule(40, 90)` → 180 cm；只有 `Capsule + VisualRoot` | **无 `USkeletalMeshComponent`** |
| 骨骼 / 动画 / AnimBP | 不存在 | 待接 |

### 1.2 第三方 CC0 资产（实测，逐个解析 GLB 得到）

| 文件 | 网格 | 骨骼 | 片段数 | 关键片段 | 体积 |
|---|---|---|---|---|---|
| `astronaut_Quaternius_OgeSH89Nmx.glb` | 2 | **43** | 18 | `Idle` `Run` `Walk` **`Duck`** `Jump` `Jump_Idle` `Jump_Land` `Wave` `Yes` `No` | 0.72 MB |
| `astronaut_Quaternius_zbtPq4dOJL.glb` | 2 | 43 | 18 | 与上行**结构完全相同**（同款换色） | 0.67 MB |
| `astronaut_Quaternius_3hC2i0CTuO.glb` | 4 | 248 | 24 | `Run` **`Run_Left`** **`Run_Right`** `Run_Back` `Roll` **`Kick_Left`** **`Kick_Right`** | 1.86 MB |
| `quaternius_fox_cc0.glb` | 1 | 51 | 24（**12 段重复前缀**，实为 12 段） | `Idle` `Idle_2` `Walk` **`Gallop`** `Gallop_Jump` | 0.94 MB |
| `astronaut_Polygonal-Mind_*.glb` ×3 | 1 | 0 | 0 | 静态，包围盒仅 **1–5 cm**（小摆件） | 1.7 MB |
| ~~`astronaut_PW-Wu_*`~~ / ~~`astronaut_Poly-by-Google_*`~~ | 静态、无骨骼 | 0 | **CC-BY（有署名义务）→ 已删除** | — |

**已清理**：删除 2 个 CC-BY 模型与 4 张搜索用预览图，`Content/Models` 从 11 MB 降到 5.8 MB。

---

## 2. 资产决策

| 角色 | 采用 | 理由 |
|---|---|---|
| **主角宇航员** | `astronaut_Quaternius_OgeSH89Nmx`（43 骨，含 `Duck`/`Jump`） | 骨骼数合理（248 骨那套偏重）；`Duck` 可直接当蹲下，`Jump` 系列可支撑跳跃 |
| （备选/换色） | `zbtPq4dOJL` | 与上行同结构，**M1 时在 Blender 里各渲一张对比后再定**，另一份删掉 |
| **拾光狐狸** | `quaternius_fox_cc0`（51 骨，`Idle`/`Gallop`） | 现成的待机与奔跑 |
| **云鲸** | 仍需自制 | 没有匹配的 CC0 巨兽；按设计文档 §5「低模 + 尾巴/鳍少量骨骼」 |
| 自制宇航员/狐狸 | 转为**可选的重定向目标** | 见 §2.2 |

**许可**：Quaternius 全部为 **CC0**（免署名、可商用）。即便如此仍在 `art/thirdparty/LICENSE.md` 记录来源链接与获取日期——CC0 不要求署名，但**来源可追溯**是工程要求。

### 2.1 代价：必须说清的两点

1. **美术方向改变**。这套是**低模写实向的科幻角色**（材质名 `SciFi_Main`、`SciFi_MainDark`、`Grey`；片段含 `Gun_Shoot`/`Punch`/`Death`/`Sword_Slash`），与设计文档「圆润低卡通、暖色小小旅人」以及「狐狸与相机上的玩偶同一形象」**不一致**。这是采用现成资产的既定代价。
2. **七动作里的核心动作仍然缺**（见 §4）。**采用 CC0 并不能免掉 Blender 工作**，只是把「从零做 13 段」降为「补 3 类短片段」。

### 2.2 保留的改进余地：重定向

本方案的 **UE 侧（§6）与 C++/AnimBP 契约与用哪套网格无关**。所以后续若想拿回自制造型，只需把 CC0 的骨架与动画**重定向**到自制网格上，UE 侧无需改动。因此这个决定**不是单向门**。

---

## 3. 仍需冻结的约定

导入的第三方资产**不会自动符合** UE 要求，必须先归一化——实测它们同样不满足（脚底不在原点、朝向未知、厘米/米未知）。

| 约定 | 值 | 检查方式 |
|---|---|---|
| 单位 | 导出/导入后角色高 **180 cm** | 导入后断言包围盒高 |
| 原点 | **双脚落点、Z = 0** | 断言 `min_z ≈ 0` |
| 朝向 | Blender 面向 **-Y** → UE 面向 **+X** | 导入后断言面罩朝 +X |
| 左右 | 面朝 -Y 时角色**左手在 +X** | 真人抬左腿 → 角色抬左腿（§8） |
| 命名 | `SK_/SKEL_/A_/ABP_/SM_/M_` 前缀；左右后缀 `_l`/`_r` | 导入后核对资产名 |
| 狐狸尺寸 | 高 **55 cm** | 断言 |

> 归一化的具体做法：在 Blender 里导入 GLB → 重设原点、旋转到 -Y、按目标高度缩放 → `apply` 全部变换 → 导出 FBX（`global_scale=100`）。

---

## 4. 片段映射表（七动作 → 现有片段）

| 游戏动作 | 现有可用片段 | 判定 |
|---|---|---|
| 跑步 | `Run` | ✅ 直接可用 |
| 站立 / 待机 | `Idle` | ✅ |
| 蹲下 | `Duck` | ✅ 语义吻合 |
| 往左跳 / 往右跳 | `Run_Left` / `Run_Right`（在 248 骨那套里） | ⚠️ **跨骨架**（62 vs 43 骨），需重定向或补做 |
| 抬左腿 / 抬右腿 | `Kick_Left` / `Kick_Right`（同上） | ⚠️ 踢 ≠ 跨步，且跨骨架 |
| **开合跳** | **无** | ❌ **必须补做** |
| 狐狸待机 / 跑 | `Idle` / `Gallop` | ✅ |

**结论：必须补做 3 类短片段**（都在已采用的 43 骨骨架上做，工作量远小于从零）：

1. **开合跳**：`A_Hero_Jack_Start`（8 帧）/ `_Hold`（6 帧循环）/ `_End`（8 帧）——对应 `phase` 的 Begin→Complete，Begin 打开、Complete 收回，**只有打开阶段计分**（设计文档硬要求）。
2. **抬腿**：`A_Hero_LegLift_Left_Up/_Down`、`_Right_Up/_Down`（各 6 帧）——跨步而非踢。
3. **换道跳**：`A_Hero_Lane_Left` / `_Right`（各 11 帧）——侧向蹬地 + 落地，**在自家骨架上做**，避免跨骨架重定向。

补做方式：在 Blender 里导入已采用的骨架，用**姿态关键帧**（旋转 + 少量位移）逐段做。这些动作都是简单的四肢旋转，不需要写实表演。

---

## 5. Blender 侧实现

```
art/thirdparty/cc0/     astronaut_quaternius.glb / fox_quaternius.glb + LICENSE.md
art/blender/
  lib_pipeline.py       共用：导入 / 归一化 / 断言 / 导出
  normalize_hero.py     归一化 CC0 宇航员（原点、朝向、缩放、命名）+ 自检 + 导出 FBX
  normalize_fox.py      同上（狐狸）
  author_clips.py       在归一化后的骨架上补做 §4 的 3 类片段 + 自检 + 导出
  build_whale.py        云鲸（唯一仍需从零建模+绑骨的资产）
```

**每个脚本的自检断言**（失败即不产出文件）：

- 骨架存在且骨骼数 == 43（英雄）/ 51（狐狸）
- 脚底 `abs(min_z) < 1e-3`
- 朝向：面罩/鼻子的世界 X < 0（已转 -Y）
- 高度 == 180 / 55 cm ±1 cm
- 片段数 == 预期，且**片段名符合 §3 命名规范**
- 导出文件存在且体积在合理区间（防"导出空文件"）

---

## 6. UE 侧实现

### 6.1 目录规范

```
Content/StarJourney/Characters/Hero/   SK_Hero, SKEL_Hero, A_Hero_*, ABP_Hero
Content/StarJourney/Characters/Fox/    SK_Fox, SKEL_Fox, A_Fox_*, ABP_Fox
Content/StarJourney/Characters/Whale/  SK_Whale, SKEL_Whale, A_Whale_Float_Loop
Content/StarJourney/Props/             Stations/ Nature/ Sky/
```

用 **`Content/Python/import_art.py`** 脚本导入（新增 PS1 动作 `ImportArt`），不手工拖拽——手工导入不可复现。

| 导入设置 | 值 | 原因 |
|---|---|---|
| Import Uniform Scale | 1.0 | 缩放已在导出时烘焙为厘米 |
| Import Animations | 是 | 每段 take → 一个 AnimSequence |
| Create Physics Asset | 是 | 留给后续受击/布娃娃；**运行时不用它做碰撞** |
| Import Materials | 是 | 见 §6.2 |

### 6.2 材质

CC0 资产自带贴图材质（`Atlas` / `SciFi_*` / `Main`+`Eyes`），导入后**重父级到 `M_StarMaster`**（含 BaseColor/Roughness/Emissive 参数的母材质），便于统一调色向设计文档的暖色调靠拢——这是在不改模型的前提下**最省力地把画风拉回**的手段。

### 6.3 Pawn 接入

- 新增 `USkeletalMeshComponent* Mesh`，`SetupAttachment(Capsule)`，与 `VisualRoot` 同位。
- **保留 `VisualRoot`**：没配骨骼网格时仍用占位，便于美术未就位时继续开发。
- `ApplyVisualOffset()` 的跳跃弧线/蹲下俯身继续作用在视觉根上；换道已改 Pawn 本体，骨骼网格挂胶囊自然跟随。
- 骨骼网格 `SetCollisionEnabled(NoCollision)`：碰撞权威仍是胶囊。
- AnimBP 类用 `UPROPERTY(EditDefaultsOnly) TSubclassOf<UAnimInstance>` 暴露。

### 6.4 AnimBP / Montage 契约（冻结）

| 内容 | 载体 | 理由 |
|---|---|---|
| 待机 / 跑步 | 状态机 `Idle ⇄ Run` | 长驻状态，拉取 `IsRunning()` |
| 蹲下 | 状态机 `DuckIn → DuckLoop → DuckOut` | 与 `SquatAlpha` 连续量对应 |
| 换道、抬腿、开合跳 | **Montage**，`Begin` 时由 C++ 播放 | 离散有时限；状态机追踪易出竞态 |

```cpp
UENUM(BlueprintType)
enum class EStarAnimState : uint8 { Idle, Run, Squat, Jack, LaneLeft, LaneRight, LegLeft, LegRight };

UFUNCTION(BlueprintPure) EStarAnimState GetAnimState() const;
UFUNCTION(BlueprintPure) float GetSquatAlpha() const;
UFUNCTION(BlueprintPure) bool  IsRunning() const;              // 已有

// 资产引用由编辑器指派，C++ 不硬编码资产路径
UPROPERTY(EditDefaultsOnly, Category="Star|Anim") TObjectPtr<UAnimMontage> JackMontage;
UPROPERTY(EditDefaultsOnly, Category="Star|Anim") TObjectPtr<UAnimMontage> LaneLeftMontage;
UPROPERTY(EditDefaultsOnly, Category="Star|Anim") TObjectPtr<UAnimMontage> LaneRightMontage;
UPROPERTY(EditDefaultsOnly, Category="Star|Anim") TObjectPtr<UAnimMontage> LegLeftMontage;
UPROPERTY(EditDefaultsOnly, Category="Star|Anim") TObjectPtr<UAnimMontage> LegRightMontage;
```

### 6.5 狐狸与云鲸

- 狐狸：`AStarCompanionFox : AActor`，骨骼网格 + `ABP_Fox`，位置用弹簧插值跟随 Pawn 固定偏移（设计文档 §6「插值跟随固定偏移」）；状态只需 `Idle`/`Gallop`。
- 云鲸：`AWhaleDrifter : AActor`，骨骼网格 + `A_Whale_Float_Loop` 单曲循环，沿 Spline 缓慢飞行（6–8 秒浮动）。

### 6.6 场景件替换占位

`build_scene.py` 现在用 `/Engine/BasicShapes` 与 `LP_sci_fi_island` 占位。美术就位后**只换映射表**（`mesh()`/`prop()` 已是统一入口），逐项可回退，不阻塞其它项。

---

## 7. 版本控制

| 内容 | 入库 | 说明 |
|---|---|---|
| `.blend`（自制源） | ✅ | 源真值 |
| 第三方 CC0 `.glb` | ✅ | 已采用的角色来源 |
| `art/thirdparty/LICENSE.md` | ✅ | 来源与许可可追溯（CC0 亦记录） |
| Blender 脚本 / UE 导入脚本 | ✅ | 保证资产**可重建** |
| 导出的 `.fbx` | ✅ | 让未装 Blender 的人也能导入 |
| `.uasset` | ❌ | 二进制、体积大；由 `ImportArt` 生成（与 `Content/StarJourney/` 已被 gitignore 的现状一致） |

> 已删除的 CC-BY 文件仍留在 git 历史里。要去掉需重写历史——**破坏性操作，未执行**；如你需要再说。

---

## 8. 验证与验收

| 阶段 | 自动断言 | 人工目视 |
|---|---|---|
| 归一化 | 骨骼数、脚底 z=0、面朝 -Y、高度=180/55 cm | 与自制模型并排看比例 |
| 片段 | 片段数与命名符合 §3/§4 | 每段在 Blender 里播一遍 |
| 导入 | 资产存在；骨骼网格高 = 180 cm | 静态摆放比例正确 |
| 朝向 | 导入后**面罩朝 +X** | Play 时朝前跑，不侧身 |
| 循环 | 首尾帧姿态差 < 阈值 | 跑步/狐狸跑无跳帧 |
| 玩法联动 | `Begin` 播 Montage、`Complete` 收尾 | **真人抬左腿 → 角色抬左腿**（左右不反，设计文档硬要求） |
| 蹲下 | `SquatAlpha` 与动画权重一致 | 蹲下保持到真实站起，不自动弹起 |
| 开合跳 | Begin 打开 / Complete 收回 | **只有打开阶段计分，不重复计数** |

---

## 9. 里程碑与分工

| # | 里程碑 | 内容 | 谁 |
|---|---|---|---|
| **M1** | 归一化 + 导入跑通 | 选定制服（渲染对比后定）、归一化两个角色、UE 脚本导入、看到 180 cm 角色站对位置朝对方向 | Blender 侧我可验证；UE 侧需你编译 |
| **M2** | 补做片段 + 接入 Pawn | §4 的 3 类片段 + §6.3/6.4 接入 | 同上 |
| **M3** | 狐狸 / **M4** 云鲸 | 跟随 Actor / 自制云鲸 | 可并行 |
| **M5** | 场景件替换 | §6.6 逐项替换 | 可并行 |
| **M6** | 二、三关内容 | 关卡数据文本驱动 | M5 |

**M1 是关键路径**：单位/原点/朝向三个坑都在这一步暴露。

---

## 10. 风险与对策

| 风险 | 对策 |
|---|---|
| 单位/缩放错（大或小 100 倍） | 导出 `global_scale=100` + 导入后断言 180 cm |
| 朝向错 90° | 归一化转向 -Y + 导入后断言面罩朝 +X |
| 原点不在脚 → 陷地/悬空 | 重设原点 + 断言 `min_z≈0` |
| **跨骨架重定向失败**（248 骨 → 43 骨） | 不依赖它：换道片段**在自家骨架上补做** |
| 43 骨骨架没有手指/次级骨骼，某些片段姿态怪异 | M1 目视检查；必要时只用其躯干动画 |
| 画风偏离设计文档 | `M_StarMaster` 统一调色拉回暖色；必要时走 §2.2 重定向 |
| 第三方资产许可 | 已清 CC-BY；CC0 仍记录来源 |
| 重导入覆盖手工调整 | 手工调整只做在母材质/AnimBP 层 |
| **我无法编译 UE**（本机无引擎、无 Xcode） | UE 侧仅静态审查；首次编译报错你贴回，我逐个修 |
| **虚假验证声明** | 本方案所有数字均为本地实测；后续每个 agent 必须**给出可复核的证据**，不得声称未执行的验证 |

---

## 11. 下一步（建议立刻做 M1）

1. 在 Blender 里渲染 `OgeSH89Nmx` 与 `zbtPq4dOJL` 对比，定下制服款式，删掉另一份；
2. 归一化两个角色（原点/朝向/缩放/命名）+ 自检 + 导出 FBX；
3. 写 `import_art.py` + PS1 `ImportArt` 动作；
4. 你在 Windows 跑一次导入，把结果发我；
5. 通过后做 M2 的 3 类补做片段与 Pawn 接入。

# 向星而行 · UE C++ 游戏模块（StarJourney）

这是《向星而行》的**运行期游戏逻辑**，用 UE C++ 实现，可直接编译、入 Git。它把 `build_scene.py` 那个 Sequencer 播片样片，升级为**能实时玩的游戏**：三道跑酷角色 + 统一输入源（键盘 / WebSocket 体感）+ 关卡控制器 + 任务机关。

> 现有 `L_EchoForest` 播片地图保留作演示；本模块用**独立玩法地图**驱动，互不影响。

## 模块组成

| 类 | 职责 | 对应设计文档 |
|---|---|---|
| `AStarRunnerPawn` | 三道跑酷角色：自动前进、换道、蹲下、开合跳 | `ABP_Runner` |
| `UStarInputComponent` | 统一输入源：键盘现在、WebSocket 体感随后 | `UActionInputComponent` |
| `AStarLevelDirector` | 关卡控制器：任务点停靠、点灯、结算星种 | `ABP_LevelDirector` |
| `AStarStation` | 通用任务机关（邮站/灯/花台换皮即可） | `ABP_Station` |
| `AStarGameMode` | 游戏模式：绑定 Runner 为默认玩家 | — |
| `StarTypes.h` | 动作/相位/追踪状态枚举，**与 `star.proto` 数值一一对应** | §2.1 |

## 关键设计

### 1. 动作语义与 protobuf 完全对齐

`StarTypes.h` 的 `EStarAction` 数值 = `star.v1.Action`（1=蹲下 … 6=开合跳）。WebSocket 网关推来的字符串动作名（`SQUAT`/`JUMPING_JACK`…）经 `ActionFromString` 一一映射。WebSocket 由 Go 服务在 `127.0.0.1:50052/ws/input?generation=N` 提供（见仓库根 README）。

### 2. 反延迟：动作当帧生效

`AStarRunnerPawn::HandleAction` 收到 Begin 的**同一帧**就改运动状态——没有队列、没有轮询定时器、没有 Sequencer。键盘按下即 Begin，这就是"按左移键立即换道"的实现路径（区别于之前 1–2 秒延迟的链路）。

### 3. UE 只做四项输入判断

`HandleAction` 严格对应文档 §2.2：

1. generation 由输入组件检查（`HandleStreamEvent`）；
2. 玩法当前是否允许（`CanStartAction`：最外道不能向外跳）；
3. Begin 需 Ready 且无进行中动作；
4. Complete/Cancel 只匹配当前动作，**不查 Ready**（否则开始抬腿后 Ready=false 会拦住完成）。

### 4. 换道移动本体，跳跃/蹲下用视觉偏移

换道直接改 Pawn 世界 Y（碰撞、机关触发都依赖真实位置）；跳跃弧线与蹲下俯身叠加在 `VisualRoot` 上，胶囊体保持稳定脚印。蹲下**持续到真实站起**（Complete 才混出），不由动画自动结束。

### 5. 任务点夹紧停车

`StarLevelDirector::UpdateStops` 在 `StopX` 处**硬夹紧**——掉帧也不能跳过任务点。玩家做出配置的动作（默认开合跳）→ 点亮 → 继续前进；全部任务完成且越过 `FinishX` → 结算星种、统计各动作完成次数并写入存档。

### 6. 固定后视相机由 Pawn 自己持有

`AStarRunnerPawn` 带一个 `UCameraComponent`，每帧显式设定**世界**位置与旋转（`CameraBackOffset=1350`、`CameraHeight=440`、`CameraPitch=-6`、`CameraFov=55`，对齐原播片机位）。关键在于相机的世界 Y 锁在 `CenterLineY`（出生时的中心线）而**不是**角色当前 Y —— 所以换道时镜头不随角色左右摆动，符合设计文档「横向主要跟道路中心，角色换道时镜头不跟着急摆」。相机挂在自己身上，视角必然绑到玩家，不再依赖关卡里的 CameraActor。

### 7. 存档链路（UE → Go → SQLite）

`AStarLevelDirector` 自带一个 `UStarSaveQueueComponent`（待提交队列）；`Settle()` 时组装 `FStarRun` → **先持久化入队** → 再 `Flush()`：

- `run_id` 是本局一次性 UUID，重试复用同一个，因此「服务已提交但回包丢失」的重试会命中幂等、返回原记录。
- `active_ms` 取本局游戏时钟；`action_counts` 是各动作**完整周期**次数。
- 队列语义与 Go 的 `client/savequeue` 逐条一致：凭返回 run_id 匹配才移除、损坏文件不覆盖、临时文件+原子替换、失败停止本轮并保留余项。
- 存档走 HTTP：`POST http://127.0.0.1:50052/api/save`；启动时用 `GET /api/progress` 读取解锁状态（`Progress` / `OnProgressLoaded`）。
- **AutoDemo 不入队**（设计文档：演示不写真实进度）。

### 8. HUD（纯 C++ Slate，无 UMG 资产）

`AStarHUD` 在 `BeginPlay` 把 `SStarHudWidget` 加入视口，每帧从 Pawn / Director 取数刷新：星光数、任务进度 `0/3`、当前动作（**色块 + 中文名**，满足「不只靠颜色提示」）、追踪状态、任务点所需动作提示、暂停提示。

暂停用真正的引擎暂停。这条闭环依赖四处配合，**缺一即失效**：

1. `AStarPlayerController` 构造里 `bShouldPerformFullTickWhenPaused = true`（缺它则暂停时控制器根本不走完整 tick）；
2. `SetupInputComponent` 里 `InputComponent->bExecuteWhenPaused = true`，**之后**再绑 Esc；
3. `AStarHUD` 构造里 `PrimaryActorTick.bTickEvenWhenPaused = true`（否则暂停后界面不刷新，看不到「已暂停」）。

### 9. 玩法地图（免蓝图）

`Content/Python/build_play_level.py` 生成 `L_EchoForest_Play`：复制播片地图的场景资源，**删掉** Sequencer 导演、播片相机与 `05_Travellers` 占位角色，放 `PlayerStart` + 1 个 Director + 3 个 Station（三盏路灯各需一次完整开合跳），并把玩法地图的 GameMode 覆盖为 `AStarGameMode`、**同时把播片地图钉回 `GameModeBase`**（否则播片地图会继承全局玩法模式，在演示里生成一个 Pawn）。

Director 通过 `bAutoInitialize` 自己发现 Pawn 与 Station 并接线，**因此地图不需要任何蓝图胶水**。

```powershell
.\Manage-StarJourney.ps1 -Action PlayLevel   # 生成/重建玩法地图
.\Manage-StarJourney.ps1 -Action Play        # 播放
```

## 在 Windows 上编译

前置：UE 5.8（源码或启动器版均可）、Visual Studio 2022（含 "使用 C++ 的游戏开发" 工作负载）。

```powershell
# 方式一：右键 .uproject → Generate Visual Studio project files，然后
#   打开 StarJourney.sln，以 Development Editor 配置构建 StarJourneyEditor。
# 方式二：命令行生成工程文件：
& "D:\UE\UE_5.8\Engine\Build\BatchFiles\Build.bat" StarJourneyEditor Win64 Development `
  "D:\UE\Projects\StarJourney\StarJourney.uproject" -waitmutex
```

> 仓库里 `Source/` 是源码；编译产物 `Binaries/`、`Intermediate/` 已被 `.gitignore` 排除。第一次编译前需先把 `unreal/StarJourney` 同步到本机工作工程（见上层 `Manage-StarJourney.ps1`），或直接把 `Source/` 拷进工作工程根目录再生成工程文件。

### 编译失败排查（据实际日志）

**症状：UBT 约 1 秒即失败，报 `RulesError`，且根本没编到我们的代码**

```
Unable to instantiate module 'SwarmInterface': Could not find NetFxSDK install dir;
this will prevent SwarmInterface from installing.
Result: Failed (RulesError)
Total execution time: 1.00 seconds
```

**原因**：`SwarmInterface` 属于 **Editor target 的开发者工具**，它需要 **.NET Framework SDK 4.6+**。机器上只有 .NET 10（Core），两者不是一回事。

**两种解法**：

1. **想立刻验证 C++ 是否编得过 → 编 Game target**（推荐，无需装任何东西）：

   ```cmd
   "%ENGINE_PATH%\Engine\Build\BatchFiles\Build.bat" StarJourney Win64 Development ^
     "%PROJECT_FILE%" -WaitMutex
   ```

   Game target **不构建开发者工具**，因此整条 `Launch → UnrealEd → PropertyEditor → …` 依赖链被绕开（上面的错误追溯里正是这条链）。StarJourney 模块是 `Runtime` 类型，Game target 一样会编译它，足以确认代码本身能否通过。

2. **要能打开编辑器 → 装 .NET Framework 4.8.1 Developer Pack**，然后照常编 `StarJourneyEditor`：

   ```cmd
   "%ENGINE_PATH%\Engine\Build\BatchFiles\Build.bat" StarJourneyEditor Win64 Development ^
     "%PROJECT_FILE%" -WaitMutex
   ```

   验证安装：`dir "C:\Program Files (x86)\Windows Kits\NETFXSDK\"` 应出现 `4.8` / `4.8.1`。

**另外两条容易踩的坑**：

- **`WebSockets` 插件不能从 `.uproject` 里删掉**。`StarJourney.Build.cs` 依赖 `WebSockets` 模块，`StarInputComponent.cpp` 也用了 `FWebSocketsModule`；插件被禁用而 Build.cs 仍依赖它，UBT 会直接报找不到模块。`Manage-StarJourney.ps1` 每次同步都会用仓库版本覆盖 `.uproject`，所以**重跑一次同步即可自动修回**。
- **`.uproject` 必须是 UTF-8**。用 PowerShell 的 `Set-Content` / `Out-File` 直接改它（PS 5.1 默认写 UTF-16LE+BOM）会导致工程无法解析。改这个文件请用编辑器或 `Copy-Item`。
- 若报 `TObjectPtr is not a member of UE`，**不要**把 `TObjectPtr<>` 换成裸指针——`TObjectPtr` 在 UE5 完全合法，那只会掩盖真正的原因（通常是包含顺序或头文件缺失）。

## 键盘操作（默认）

| 键 | 动作 | 游戏作用 |
|---|---|---|
| A / D | 往左跳 / 往右跳 | 向相邻道路换道（最外道不能再向外） |
| S（按住） | 蹲下 | 穿过低树枝/花藤/云拱门；**松开才算站起** |
| Q / E（按住） | 抬左腿 / 抬右腿 | 跨过对应脚侧障碍、触发脚印机关 |
| 空格 | 开合跳 | 越过缺口、点亮机关、唤醒星种 |
| Esc | 暂停 / 继续 | 引擎暂停；暂停时 HUD 仍刷新并显示提示 |

## 接体感（下一步）

`UStarInputComponent::ConnectGestures("ws://127.0.0.1:50052/ws/input")` 即可接入 Go 网关的动作流；组件会自动带上递增的 `generation`。键盘与体感共用同一套 `HandleAction`/`HandleTracking`，玩法代码不变。

## 待落地（后续批次）

- **角色骨骼与 AnimBP**：当前角色表现是胶囊体 + 视觉占位（`Content/Models` 里的宇航员/狐狸是静态低模）。六个动作与狐狸待机的骨骼动画需在 Blender 绑骨 + 权重 + 动画，随后 Pawn 换成 `USkeletalMeshComponent` 并由 AnimBP 状态机驱动。
- **第二、三关内容与场景件美术**：云鲸、邮站/风车/信封/花台、云桥、巨行星、群山剪影；关卡数据改为文本配置驱动。
- **文档后置项**：选关与解锁页、纪念页媒体表、局中断点续玩、设置系统、UE 奖励演出状态。

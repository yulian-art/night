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

`StarLevelDirector::UpdateStops` 在 `StopX` 处**硬夹紧**——掉帧也不能跳过任务点。玩家做出配置的动作（默认开合跳）→ 点亮 → 继续前进；全部任务完成且越过 `FinishX` → 结算星种并统计各动作完成次数（供 `SaveRun`）。

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

## 键盘操作（默认）

| 键 | 动作 | 游戏作用 |
|---|---|---|
| A / D | 往左跳 / 往右跳 | 向相邻道路换道（最外道不能再向外） |
| S（按住） | 蹲下 | 穿过低树枝/花藤/云拱门；**松开才算站起** |
| Q / E（按住） | 抬左腿 / 抬右腿 | 跨过对应脚侧障碍、触发脚印机关 |
| 空格 | 开合跳 | 越过缺口、点亮机关、唤醒星种 |

## 接体感（下一步）

`UStarInputComponent::ConnectGestures("ws://127.0.0.1:50052/ws/input")` 即可接入 Go 网关的动作流；组件会自动带上递增的 `generation`。键盘与体感共用同一套 `HandleAction`/`HandleTracking`，玩法代码不变。

## 待落地（需蓝图/编辑器，不在 C++ 范围）

- 玩法地图 `L_EchoForest_Play`：把 `L_EchoForest` 的场景资源复制一份，World Settings 的 GameMode 设为 `AStarGameMode`，放一个 `AStarLevelDirector` 并在关卡蓝图里 `InitializeRun(Runner, Stations)`。
- 宇航员/狐狸骨骼网格与 AnimBP：当前 Pawn 用胶囊体 + 视觉占位，正式角色动画需美术资产。
- 固定后视相机绑定玩家视角、HUD（星光、任务进度、动作图标）。

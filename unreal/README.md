# 向星而行 · UE 场景样片

原生 UE 5.8 场景，使用本机 `FlyingSc0fe89709cde4V1` 素材包的树、蘑菇、晶体、路灯、浮岛、天文台和飞船。仓库保存工程配置与生成脚本；素材包和生成的二进制资产保存在 Windows 工作工程中，不加入 Git。

## 打开与播放

本机工作工程：`D:\UE\Projects\StarJourney\StarJourney.uproject`。

- 双击工作工程中的 `Open-Editor.cmd` 打开编辑器；默认地图是 `L_EchoForest`。
- 在编辑器按 Play 播放，或双击 `Play-Demo.cmd` 独立窗口播放 30 秒循环样片。
- 在编辑器按 Esc 结束播放；独立窗口用 Alt+F4 退出。
- 打开 `/Game/StarJourney/Cinematics/LS_EchoForest_30s`，在 Sequencer 中拖动时间轴检查动作和点灯。打开相机切换锁定可查看实际镜头。

这是场景和演出原型：三道道路、固定后视相机、巨行星、三层山景、森林浮岛、三座星灯，宇航员与狐狸的组合网格占位模型。演示包含前进、一次左右换道、蹲下、三次停靠开合跳与点灯。

当前播放由 Sequencer 时间轴驱动，尚未实现键盘动作、姿态识别接线、正式任务判定或存档。演示不调用 Go 服务、不修改真实通关进度。组合网格动画不等同于已制作角色骨骼或 AnimBP。

## 重建场景

在 Windows PowerShell 中执行（脚本路径可用本仓库 WSL UNC 路径）：

```powershell
.\Manage-StarJourney.ps1 -Action Inspect
.\Manage-StarJourney.ps1 -Action Build
.\Manage-StarJourney.ps1 -Action Capture
.\Manage-StarJourney.ps1 -Action Validate
.\Manage-StarJourney.ps1 -Action Open
```

脚本默认使用：

| 项目 | 路径 |
| --- | --- |
| 引擎 | `D:\UE\UE_5.8` |
| 原始素材 | `D:\UE\VaultCache\FlyingSc0fe89709cde4V1\data` |
| 工作工程 | `D:\UE\Projects\StarJourney` |

可传 `-EngineRoot`、`-VaultRoot`、`-ProjectRoot` 覆盖默认路径。启动器支持 `STAR_UE_ROOT` 环境变量。脚本拒绝覆盖没有 `.starjourney-managed` 标记的现有目录；不会修改 VaultCache。

`Build` 会重建 `00_` 至 `07_` 文件夹内的生成 Actor 和同名材质、演示序列。重建前自动将旧的 `Content/StarJourney` 备份到 `Saved/SceneBackups/<时间戳>`。手工美术迭代请先另存地图和序列，或直接修改生成脚本再重建。工作工程的 Config 与 Python 脚本也从仓库同步。

## 目录与验证输出

| 内容 | UE 路径 / 文件 |
| --- | --- |
| 生成地图 | `/Game/StarJourney/Maps/L_EchoForest` |
| 30 秒循环 | `/Game/StarJourney/Cinematics/LS_EchoForest_30s` |
| 原始素材 | `/Game/LP_sci_fi_island` |
| 主题材质 | `/Game/StarJourney/Materials` |
| 资产真实包围盒 | `Saved/SceneReports/asset_inventory.json` |
| 生成统计 | `Saved/SceneReports/build_report.json` |
| GPU 渲染截图与时间点 | `Saved/SceneReports/*.png`、`capture_report.json` |
| 实际 Play 自动播放与循环验证 | `Saved/SceneReports/play_report.json` |
| 引擎日志 | `Saved/Logs/Build.log`、`Capture.log`、`Validate.log` |

使用固定随机种子、厘米单位和 sRGB → 线性颜色转换。关闭 Lumen、运动模糊和自动曝光，采用主光、补光、天空光及任务局部点光。Python 只在编辑器构建阶段使用；运行时演示依赖引擎内置 Level Sequence。

接口参考：[Epic Sequencer Python](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MovieSceneObjectBindingID)、[Epic 截图 API](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AutomationLibrary)。实现已按本机 UE 5.8.2 的接口验证。

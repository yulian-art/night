# 向星而行 · Go 本地服务

依据 [UE 实现架构与设计](docs/向星而行_UE实现架构与设计.md)，实现本机动作消息桥接和 SQLite 通关存档。仓库包含跨语言 Protobuf 协议、生成的 Go 客户端/服务端代码、可运行服务、模拟识别端与测试。

## 启动与验证

环境：Go 1.26+、C 编译器（SQLite 驱动使用 CGO，`CGO_ENABLED=1`）。只运行/构建服务不需要 protoc。

```sh
go mod download
make test
make build
./bin/star-service -listen 127.0.0.1:50051 -ws-listen 127.0.0.1:50052 -db data/star.db
```

在另一终端运行（需没有其他 UE/识别端连接）：

```sh
./bin/star-smoke
```

输出 `Ready → JumpingJack Begin → Complete → Ready` 和三关进度；不打开相机、不写真实成绩。服务仅允许 loopback IP，提供标准 gRPC Health 服务；Ctrl+C 最多等待 3 秒退出。

## UE 接入：WebSocket/JSON 网关

服务除 gRPC（`127.0.0.1:50051`，Python 识别端用）外，还在 `127.0.0.1:50052` 暴露一个 **WebSocket/JSON 网关**，供 UE 用内置 WebSocket 插件直连，无需在 UE 中集成 gRPC。

```
GET ws://127.0.0.1:50052/ws/input?generation=<uint64>
```

- `generation` 由 UE 在连接参数中传入，语义与 gRPC `WatchInput` 完全一致（递增编号；开始输入/进出任务/暂停恢复/点击完成/重连时换号）。
- 连接后服务端按序推送 JSON 事件，每条对应一个 `InputEvent`：

```json
{"tracking": {"generation": "1790...", "state": "READY"}}
{"action":   {"generation": "1790...", "action": "JUMPING_JACK", "phase": "BEGIN"}}
```

- `generation` 以十进制**字符串**传输（JSON 数字放不下 uint64）。`state` ∈ `LOST/NOT_READY/READY`；`action` ∈ `SQUAT/LEFT_LEG/RIGHT_LEG/JUMP_LEFT/JUMP_RIGHT/JUMPING_JACK`；`phase` ∈ `BEGIN/COMPLETE/CANCEL`。
- 出错（编号被替换、队列溢出、识别端断线）时服务端先发一条 `{"error": ..., "code": ...}` 再关闭连接，UE 据此暂停并以新 generation 重连。

## UE 接入：存档 HTTP 接口

存档走同一 `50052` 端口上的 HTTP+JSON（UE 无 gRPC 插件）：

```sh
POST http://127.0.0.1:50052/api/save
{"run_id":"<uuid>","level_id":2,"score":12,"active_ms":31200,"action_counts":{"2":3,"6":1}}
→ 200 {"run":{...原样返回已保存记录...}}

GET  http://127.0.0.1:50052/api/progress
→ 200 {"levels":[{"level_id":1,"completed":true,"best_score":57,"unlocked":true}, ...]}
```

- 字段与 `star.v1.Run` / `LevelProgress` 一一对应；`action_counts` 键是数值 Action（1–6），值是**完整周期次数**（不含 Begin/Cancel）。
- 与 gRPC 的 `SaveRun` / `GetProgress` **共用同一个 `storage.Store` 和同一套错误分类**，两条通路不会各自漂移。
- **幂等**：相同 `run_id` 重试返回**首次保存**的记录，即使本次 payload 不同，也不会改写存档或另一关进度 —— 这是客户端待提交队列的安全前提。
- 校验：`level_id` 必须 1–3、分数与时长非负、`run_id` 非空且 ≤128 字节；**未知字段会被拒绝**（避免拼写错误静默写入错误成绩）。非法输入 400，动词不对 405。
- `unlocked` 是派生值：第 1 关恒解锁，第 N 关取决于第 N−1 关 `completed`。

gRPC 通路（`127.0.0.1:50051`）继续保留，供 Python 识别端与任何 gRPC 客户端使用。

重新生成协议需要 protoc（已验证 3.21.12）及固定版本 Go 插件：

```sh
make tools
make generate
```

生成文件已提交到源码目录，不要手改。C++ / Python 接入方直接从同一份 [star.proto](proto/star/v1/star.proto) 生成客户端。Go module 暂用本地名 `night`，确定仓库发布路径后再统一调整。

## 目录

- `proto/star/v1`：协议定义；`gen/star/v1`：生成的 Go 代码。
- `internal/input`：单识别端、单 UE 的有序消息队列、generation 隔离和周期检查。
- `internal/storage`：两张 SQLite 表及事务化幂等结算。
- `internal/service`：gRPC 接口、`ws_gateway.go`（WebSocket 推输入）、`http_api.go`（HTTP 存档）；`cmd/star-service`：进程入口。
- `client/savequeue`：Go 客户端可复用的本地 JSON 待提交队列（UE 侧对应 `StarSaveQueueComponent`，语义一致）。
- `cmd/star-smoke`：无相机联调工具。

完整接口约定与 UE/识别运行时接线顺序见 [Go 与 Protobuf 接入说明](docs/Go与Protobuf接入说明.md)。

人体识别入口见 [recognizer 使用说明](recognizer/README.md)：Windows FFmpeg 采集 Insta360 X5 USB 画面，通过本机管道送入 WSL Python，由 MediaPipe 和动作状态机向 Go 发送识别结果。支持原生预览，无需 Windows Python、Android 或 HTML。

UE 场景入口见 [回声森林场景说明](unreal/README.md)：包含 UE 5.8 工程配置、素材导入与场景生成脚本、原生地图和 30 秒自动演示。Windows 工作工程位于 `D:\UE\Projects\StarJourney`。

UE 侧现在分成两层：`L_EchoForest` 是**播片样片**（Sequencer 驱动，原样保留）；`L_EchoForest_Play` 是**可玩关卡**，由 C++ 玩法模块（`unreal/StarJourney/Source`）实时驱动——三道跑酷 Pawn、键盘/WebSocket 双输入源、任务点机关、Slate HUD、Esc 暂停，以及结算写入存档的完整链路。构建、操作与后续批次见 [UE 玩法模块说明](unreal/StarJourney/Source/README.md)。角色骨骼动画与第二、三关内容仍待后续批次。

美术资产从 Blender 到 UE 的完整管线（单位/原点/朝向约定、骨架与动画规格、Montage 契约、导入脚本与验收判据）见 [从 Blender 建模到 UE 运行 · 实现方案](docs/从Blender建模到UE运行实现方案.md)。

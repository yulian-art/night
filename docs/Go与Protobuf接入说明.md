# Go 与 Protobuf 接入说明

实现范围依据《向星而行_UE实现架构与设计》的第 2、3 节。服务只传动作/人体状态和保存通关结果；关卡、跑道、任务步骤、暂停确认和允许动作由 UE 决定。

## 协议

`star.v1.StarService`（UE 调用）：

| RPC | 类型 | 用途 |
|---|---|---|
| WatchInput | 服务端流 | 以新 generation 开始输入；同一流依次收到状态与动作 |
| SaveRun | 一元 | 保存已通关局；相同 run_id 返回首次保存的 Run |
| GetProgress | 一元 | 返回三关 completed、best_score 与派生的 unlocked |

`star.v1.RecognizerService.Connect` 是识别适配器的双向流：向 Go 发送 `InputEvent`，同时接收 `ResetInput`。动作只含 `generation / action / phase`；状态只含 `generation / state`。六种动作加 Ready（站立）对应设计文档中的七种语义。左右按玩家身体定义，与预览镜像无关。

关卡 ID 固定为 1 风邮原野、2 回声森林、3 云鲸星海。动作计数字典只接受数值 1–6 的 Action 枚举，值为非负完整周期次数，不统计 Begin 或 Cancel。

## 输入与重置

1. 识别适配器打开 Connect，并启动独立接收循环。没有 UE 时收到 generation=0，清空待处理帧与周期状态，暂停动作输出；相机仍由原识别运行时独占。
2. UE 先更新本地 generation、清空 ActiveAction、置为 NotReady，再打开 WatchInput。第一条消息固定为该 generation 的 NotReady；Go 同时发送 ResetInput 给识别端。Go 不等待识别端才允许 UE 连入。
3. 识别端在采集帧进入处理链时绑定 generation。收到重置后丢弃旧待处理帧；已在推理的旧帧继续保留旧编号，其回调不得改变新周期状态机。Go 丢弃不属于当前 generation 的结果。
4. 新编号必须重新确认中央站稳，之后发送 `Ready → Begin → Complete/Cancel → Ready`。不能先发 NotReady 再发 Begin。Complete/Cancel 只检查是否匹配正在进行的动作，不要求 Ready。
5. 开始输入、进入/离开任务、暂停/恢复、点击完成、重连及切换输入源都增加 generation 并打开新 WatchInput；Go 终止旧流并清空其队列。普通机关步骤完成不换流。取消旧流的清理不会关闭新流。

每个 Go 进程要求 generation 非零且严格递增。UE 在跨关卡 Subsystem 持有计数器；若 UE 重启而 Go 仍运行，初始值可取当前 Unix 纳秒时间，再逐次递增（同机时间倒退时应重启本地服务或恢复持久化计数）。`star-smoke` 默认采用此方式；手动小编号可能随后被拒绝。generation 是 `uint64`，其他语言不要用会丢精度的浮点数承载。

收到 Lost 时，Go 会为尚未结束的动作补发 Cancel，再发送 Lost；Cancel 不代表蹲下后真实站起。Ready/NotReady 不能中断一个活动动作，识别端应先 Cancel。Go 检查互斥周期，UE 仍须执行文档要求的四项输入判断，尤其是 generation 和玩法允许动作判断。

暂停期间保留新 generation 的流，继续显示 Lost/NotReady/Ready；UE 根据运行阶段停止消费身体动作的玩法效果。Ready 不自动解除暂停，必须由玩家确认；确认恢复时再递增 generation。暂停逻辑不放入 Go。

## 故障约定

- 第二个识别端被拒绝（AlreadyExists）；识别端断线或协议错误会关闭当前 UE 流。UE 必须暂停、清空旧队列并以新 generation 重连，不能恢复旧动作。
- 旧 generation 被替换返回 Aborted；重复或倒退编号返回 FailedPrecondition。
- 默认队列容量 64，可用 `-queue-capacity` 修改。队列溢出终止流并返回 ResourceExhausted，不静默丢失 Complete。传输层可能已有缓冲事件，UE 在终止/重连时必须清空本地队列并检查 generation。
- 不重放、不自动重试动作流。未完成动作由玩家重新做；不要对 Connect/WatchInput 配置应用层历史重放。
- 不发送视频或关键点，没有额外姿态置信度、动作 ID、序号、关卡上下文等业务字段。

## 存档与补交

SQLite 开启 WAL、FULL 同步及 5 秒 busy timeout。`runs` 和 `progress` 在同一事务中写入；唯一 run_id 防止重复结算，best_score 只升不降。三关初始均未完成，仅第一关解锁；第 N 关解锁取决于第 N−1 关 completed。Go 接受 UE 已确认的通关结果，不验证跑道/三任务/终点条件，也不强制玩家按顺序保存。

UE 结算时生成一次唯一 run_id（建议 UUID），先追加到本地 JSON 待提交列表，再调用 SaveRun。只有返回的 Run.run_id 与待提交项匹配后才移除该项。若服务已提交但响应丢失，重试会返回原 Run，即使本次请求内容变化也不会改写存档或另一关进度。GetProgress 反映当前总进度；SaveRun 不返回会随后续局变化的进度快照。

`client/savequeue` 提供相同策略的 Go 实现，可供 Go 调试客户端使用，UE 需要在客户端落地等价队列：

```go
queue, err := savequeue.Open("data/pending-runs.json")
if err != nil { return err }
if err := queue.Enqueue(completedRun); err != nil { return err }
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()
return queue.Flush(ctx, func(ctx context.Context, req *starv1.SaveRunRequest) (*starv1.SaveRunResponse, error) {
    return client.SaveRun(ctx, req)
})
```

队列由一个进程独占，通过临时文件、文件同步、重命名替换；读取损坏 JSON 会报错，不覆盖历史记录。它保证正常进程退出/重启和 RPC 失败后的补交，不承诺所有文件系统上的断电原子性。不允许在回调里再次调用同一个 Queue。失败会停止本轮补交，尚未确认的后续局仍保留。

SaveRun 只用于正式通关，AutoDemo 不调用、不进入待提交列表。当前没有媒体表、局中断点续玩、设置系统或 UE 奖励演出状态；这些按原文后续阶段再加入。

## 验证与参考

`go test -race ./...` 覆盖有序动作周期、旧 generation 隔离、丢人取消、溢出、识别端断线、SQLite 回滚/并发幂等/重启、待提交列表故障恢复，以及通过真实 gRPC 编解码的进程内集成测试。`star-smoke` 可验证实际 TCP 服务。

协议生成和流用法参考 [gRPC Go 官方教程](https://grpc.io/docs/languages/go/basics/) 与 [Protobuf Go 代码生成说明](https://protobuf.dev/reference/go/go-generated/)，进度更新使用 [SQLite UPSERT](https://www.sqlite.org/lang_upsert.html)。

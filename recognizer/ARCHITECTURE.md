# 向星而行 · 人体识别架构说明

## 技术架构

```
Windows 端                WSL Python 端                     WSL Go 端              Windows UE
┌─────────────┐          ┌──────────────────────────┐     ┌──────────────┐      ┌──────────┐
│             │          │                          │     │              │      │          │
│  Insta360   │  USB     │  WindowsFFmpegCapture    │     │  gRPC Server │      │   Game   │
│     X5      │─────────▶│  ├─ FFmpeg.exe 子进程    │     │  (50051)     │      │  Logic   │
│  (Webcam)   │          │  ├─ DirectShow 采集      │     │              │      │          │
│             │          │  └─ stdout 二进制管道    │     │  InputHub    │◀────▶│  Player  │
└─────────────┘          │          │               │     │  ├─订阅管理  │      │  Control │
                         │          ▼               │     │  └─动作队列  │      │          │
                         │  LatestFrame (单槽缓冲) │     │              │      └──────────┘
                         │          │               │     │  Storage     │
                         │          ▼               │     │  (SQLite)    │
                         │  PoseEngine (MediaPipe)  │     └──────────────┘
                         │  ├─ CPU delegate         │            ▲
                         │  ├─ 33 关键点检测        │            │
                         │  └─ 异步推理回调         │            │
                         │          │               │            │
                         │          ▼               │            │
                         │  GestureRecognizer       │            │
                         │  ├─ 六动作状态机         │            │
                         │  ├─ Ready/NotReady       │            │
                         │  └─ Begin/Complete/Cancel│            │
                         │          │               │            │
                         │          ▼               │            │
                         │  GrpcBridge (Producer)   │────────────┘
                         │  └─ 有序事件队列         │    gRPC bidirectional
                         └──────────────────────────┘    stream (loopback)
```

## 核心设计原则

### 1. Windows 到 WSL 桥接

**为什么需要桥接**：
- X5 相机在 Windows 识别为 DirectShow 设备
- WSL 无法直接访问 Windows USB 设备
- MediaPipe 和 Go 服务均在 WSL 运行

**实现方案**：
- WSL Python 直接调用 Windows FFmpeg.exe
- FFmpeg 通过 DirectShow 采集 X5 画面
- 视频以 rawvideo (BGR24) 格式流入 stdout
- WSL Python 从管道读取二进制帧
- 零拷贝转换为 NumPy 数组

**优势**：
- 无需 USB/IP 映射
- 无需 Windows Python 环境
- 画面不经过网络，不写入磁盘
- 延迟低于 50ms (仅 WSL 内部处理)

### 2. 单槽帧缓冲机制

```python
class LatestFrame:
    def put(self, frame):
        # 新帧覆盖旧帧，永不积压
        if self._frame is not None:
            self.overwritten += 1  # 监控丢帧
        self._frame = frame
```

**关键特性**：
- 相机线程永不阻塞
- 推理线程始终获取最新帧
- 避免处理过时的输入
- 适配实时游戏交互

### 3. Generation 隔离

**问题**：暂停、重连、关卡切换时，管道中仍有旧帧的推理结果

**解决**：
```python
# 采集时绑定 generation
token = self.get_generation()  # (generation, reset_epoch)
generation, epoch = token
# ... read frame ...
frame = Frame(generation, timestamp, image, epoch)

# 观察时验证
if sample.generation != self.recognizer.generation:
    return  # 丢弃旧周期的结果
```

**保证**：
- 暂停后的误触发不会触发动作
- 新 generation 开启前，旧结果全部隔离
- Go 和 Python 通过 gRPC 同步 generation

### 4. 六动作状态机

```
初始状态: NOT_READY (generation=0, 等待 UE)

UE 连接 → generation=12345
  ↓
NOT_READY (站稳 600ms) → READY
  ↓
检测动作候选 150ms → 确认
  ↓
发送 Begin → NOT_READY (active_action = SQUAT)
  ↓
完成动作 + 回到中央 250ms
  ↓
发送 Complete → READY
```

**动作类型**：
1. `SQUAT` - 蹲下（髋关节下降 14% 体高，膝盖 < 145°）
2. `LEFT_LEG` / `RIGHT_LEG` - 单腿抬高（足部上升 12% 体高）
3. `JUMP_LEFT` / `JUMP_RIGHT` - 侧向跳跃（腾空 + 水平位移 12% 体高）
4. `JUMPING_JACK` - 开合跳（双臂上举 + 双腿分开 70% 体高）

**互斥规则**：
- 只允许一个 active action
- Lost 自动取消当前动作
- 左右跳必须回到中央才 Complete
- 不会将回中央识别为反向跳

### 5. 投影适配

**透视相机 (perspective)**：
```python
# 保持纵横比缩放，不扭曲关节角度
scale = min(target_width / w, target_height / h, 1.0)
resized = cv2.resize(image, (round(w*scale), round(h*scale)))
```

**全景相机 (equirectangular)**：
```python
# 从 2:1 经纬图采样出透视视口
longitude = arctan2(px, pz)
latitude = arcsin(py / length)
mx = (longitude/(2π) + 0.5) * width
my = (0.5 - latitude/π) * height
output = cv2.remap(panorama, mx, my)
```

**配置**：
- `projection: "perspective"` - X5 普通视图 1920×1080 MJPEG；Windows 等比例缩小至 960×540 后传入 WSL
- `projection: "equirectangular"` - X5 全景 2880×1440
- `yaw_deg`, `pitch_deg`, `horizontal_fov_deg` - 调整全景视口朝向

## 数据流时序

### 启动阶段
```
1. Python 进程启动
2. 加载 MediaPipe 模型 (pose_landmarker_lite.task)
3. 连接 Go gRPC 服务 (127.0.0.1:50051)
4. 启动 Windows FFmpeg 子进程
5. FFmpeg 打开 X5 DirectShow 设备
6. 相机线程开始采集 (generation=0, 无输出)
```

### UE 连接后
```
1. UE 调用 WatchInput(generation=时间戳)
2. Go Hub.Subscribe() 创建订阅
3. Producer 收到 Reset(generation)
4. Controller.reset() 更新状态
5. 相机帧开始标记新 generation
6. MediaPipe 推理 → 动作识别 → gRPC 发送
7. UE 收到 InputEvent 流
```

### 帧处理流程
```
Windows FFmpeg (30 FPS)
  ↓ 33ms/frame
采集线程读取 rawvideo
  ↓ <1ms
LatestFrame.put(frame)
  ↓ 主循环 take()
PoseEngine.submit(frame)
  ↓ MediaPipe 异步
33 关键点 + visibility
  ↓ 回调线程
GestureRecognizer.observe(sample)
  ↓ 状态机判定
Controller.publish(event)
  ↓ 队列
GrpcBridge.send(event)
  ↓ gRPC stream
Go InputHub.Publish()
  ↓ 验证 + 入队
UE WatchInput 迭代器
  ↓
游戏逻辑处理动作
```

## 关键文件

### Python 模块

- **capture.py** - 相机抽象、单槽缓冲、投影转换
- **windows_capture.py** - Windows FFmpeg 桥接、stdout 二进制流
- **pose.py** - MediaPipe 异步推理封装
- **gestures.py** - 六动作状态机、关节角度计算
- **controller.py** - generation 隔离、watchdog、序列化
- **transport.py** - gRPC 生产者、双向流、自动重连
- **config.py** - JSON 配置加载、路径解析
- **cli.py** - 命令行入口：run / doctor / devices（--modes 查询输入模式）/ probe（实际取帧）/ watch
- **preview.py** - OpenCV 原生预览窗口（可选）
- **types.py** - 领域类型、枚举（与 protobuf 对齐）

### Go 模块

- **internal/input/hub.go** - 单识别端 + 单 UE 订阅管理
  - `Subscribe(generation)` - UE 打开新周期
  - `Attach()` - 识别端连接，获取 Reset 通道
  - `Publish(event)` - 验证状态转换，入队或拒绝
  - generation 隔离：旧帧结果静默丢弃

### 配置文件

**config.example.json**：
```json
{
  "camera": {
    "backend": "windows-ffmpeg",
    "windows_ffmpeg": "tools/windows-ffmpeg/ffmpeg.exe",
    "windows_device": "Insta360 X5",
    "windows_video_codec": "mjpeg",
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "projection": "perspective"
  },
  "model": "models/pose_landmarker_lite.task",
  "address": "127.0.0.1:50051"
}
```

## 安全与限制

### 网络隔离
```python
def validate_address(address):
    host = address.rpartition(":")[0].strip("[]")
    if not ipaddress.ip_address(host).is_loopback:
        raise ValueError("recognizer connects only to loopback")
```

### 队列保护
```python
# 满队列 → 断开连接，不丢弃 Complete
session.events.put_nowait(event)  # raises queue.Full
# Go 端同步检查
if len(h.sub.Events) == cap(h.sub.Events) {
    return codes.ResourceExhausted
}
```

### 生命周期
- 相机线程优雅关闭：2 秒超时
- MediaPipe 关闭：2 秒超时，否则报告
- gRPC 重连：指数退避，最长 5 秒
- 推理超时：5000ms 无回调 → 进程退出

## 性能指标

### 延迟分解
- X5 相机内部缓冲：~30-60ms (不可控)
- FFmpeg 采集 + stdout 传输：<5ms
- MediaPipe CPU 推理：20-40ms (lite 模型)
- 状态机判定 + gRPC 发送：<2ms
- **总延迟**：约 60-110ms (取决于相机)

### 吞吐量
- 相机采集：30 FPS
- MediaPipe 处理：25-30 FPS (CPU)
- 单槽缓冲允许丢帧：overwritten 计数可监控

### 资源占用
- Python 进程：200-400 MB (含 MediaPipe 模型)
- FFmpeg 子进程：20-50 MB
- Go 服务：10-30 MB
- CPU：单核 40-60% (MediaPipe)

## 测试与验证

### 环境检查
```bash
cd /home/julien/night/recognizer
.venv/bin/python -m star_recognizer doctor
.venv/bin/python -m star_recognizer devices
```

### 独立验证（无 Go/UE）
```bash
.venv/bin/python -m star_recognizer run --standalone
# 终端输出 JSON 事件
# 原生窗口显示关键点 + 状态
```

### 录像回放
```bash
.venv/bin/python -m star_recognizer run --standalone \
  --video /path/to/recording.mp4
```

### 完整联调
```bash
# 终端 1: Go 服务
cd /home/julien/night
go run ./cmd/star-service -listen 127.0.0.1:50051 -db data/star.db

# 终端 2: Python 识别
cd /home/julien/night/recognizer
.venv/bin/python -m star_recognizer run

# 终端 3: 模拟 UE（临时）
.venv/bin/python -m star_recognizer watch --seconds 120
```

### 单元测试
```bash
cd /home/julien/night/recognizer
.venv/bin/python -m unittest discover -s tests -v
```

## 故障排查

### X5 无法打开
```bash
# 1. 确认 X5 在 Webcam 模式
# 2. 关闭 Windows 摄像头应用
# 3. 枚举设备
tools/windows-ffmpeg/ffmpeg.exe -list_devices true -f dshow -i dummy

# 4. 检查设备名
.venv/bin/python -m star_recognizer devices
```

### MediaPipe 推理超时
- 检查 CPU 负载：MediaPipe 使用纯 CPU
- 降低 output_width/output_height；输入 width/height 保持为设备支持的模式
- 不要在推理回调中阻塞

### gRPC 连接失败
```bash
# 确认 Go 服务运行
nc -zv 127.0.0.1 50051

# 查看 Python 错误输出
.venv/bin/python -m star_recognizer run 2>&1 | grep -i grpc
```

### 动作误识别
- 调整阈值：`config.json` 中的 `gestures` 对象
- 参考 `GestureConfig` 字段：
  - `leg_lift`: 抬腿高度阈值 (默认 0.12)
  - `squat_drop`: 蹲下深度阈值 (默认 0.14)
  - `jump_distance`: 跳跃距离阈值 (默认 0.12)
- 使用真实玩家录像校准

## 扩展方向

### GPU 加速
```python
# MediaPipe 支持 GPU delegate，需独立验证
delegate=python.BaseOptions.Delegate.GPU
# CUDA 存在不保证 MediaPipe 自动使用
```

### 多人支持
```python
# 当前 num_poses=2，但状态机只处理单人
# 扩展需修改 GestureRecognizer._features()
# 增加人物 ID 跟踪
```

### 自定义动作
```python
# 在 GestureRecognizer._classify() 添加新规则
# proto/star/v1/star.proto 增加新 Action 枚举
# 重新生成 Go/Python protobuf 代码
```

### 动作录制与回放
```python
# 保存 PoseSample 序列到 JSON
# 回放时跳过相机，直接喂给 GestureRecognizer
# 用于离线标注和阈值调优
```

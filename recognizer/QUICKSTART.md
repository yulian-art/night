# 快速启动指南

## 一、环境准备（仅首次）

```bash
cd /home/julien/night/recognizer

# 1. 创建虚拟环境并安装依赖
bash scripts/setup.sh

# 2. 下载 Windows FFmpeg（如果使用 X5）
.venv/bin/python scripts/fetch_windows_ffmpeg.py

# 3. 验证环境
.venv/bin/python -m star_recognizer doctor
```

## 二、X5 相机配置

### Windows 端操作

1. **连接 X5**：USB 数据线连接到 Windows
2. **选择模式**：X5 屏幕选择 `Webcam` 模式
3. **关闭占用**：关闭所有使用摄像头的 Windows 应用
   - Windows 相机应用
   - Teams / Zoom / 钉钉等会议软件
   - OBS / 任何流媒体软件

### WSL 端配置

```bash
# 1. 枚举设备，找到 X5 的准确名称
cd /home/julien/night/recognizer
.venv/bin/python -m star_recognizer devices

# 输出示例（从 Windows FFmpeg）：
# "Insta360 X5" (video)
# "Integrated Camera" (video)
```

```bash
# 2. 创建本地配置
cp config.example.json config.local.json

# 3. 编辑 config.local.json
# 将 camera.windows_device 改为实际设备名（必须完全匹配）
{
  "camera": {
    "backend": "windows-ffmpeg",
    "windows_device": "Insta360 X5",
    "windows_video_codec": "mjpeg",
    "width": 1920,
    "height": 1080,
    "fps": 30
  }
}
```

### 验证相机参数

```bash
# 枚举配置中 X5 支持的分辨率、帧率和编码
.venv/bin/python -m star_recognizer devices --modes --config config.local.json

# 本机实测输出：
# [dshow @ ...] vcodec=mjpeg min s=1920x1080 fps=30 max s=1920x1080 fps=30
# [dshow @ ...] vcodec=mjpeg min s=2880x1440 fps=30 max s=2880x1440 fps=30

# 不加载模型，验证完整画面能从 Windows 传入 WSL
.venv/bin/python -m star_recognizer probe --config config.local.json
```

**重要**：
- 普通视图 1920×1080 MJPEG：使用 `"projection": "perspective"`，默认等比例缩小为 960×540 后传入 WSL
- 全景 2880×1440：使用 `"projection": "equirectangular"`，需调整 `yaw_deg`, `pitch_deg`, `horizontal_fov_deg`
- 旧配置的 1280×720 输入模式在本机 X5 上不受支持；降低处理分辨率请改 output_width/output_height

## 三、独立测试（不需要 Go/UE）

```bash
cd /home/julien/night/recognizer

# 使用默认配置（示例）
.venv/bin/python -m star_recognizer run --standalone

# 使用本地配置
.venv/bin/python -m star_recognizer run --standalone \
  --config config.local.json

# 无桌面环境（无预览窗口）
.venv/bin/python -m star_recognizer run --standalone --headless

# 运行 120 秒后自动退出
.venv/bin/python -m star_recognizer run --standalone --seconds 120
```

**预期输出**：

终端显示：
```json
{"generation":"1727011234567890123","state":"NOT_READY"}
{"generation":"1727011234567890123","state":"READY"}
{"generation":"1727011234567890123","action":"SQUAT","phase":"BEGIN"}
{"generation":"1727011234567890123","action":"SQUAT","phase":"COMPLETE"}
{"generation":"1727011234567890123","state":"READY"}
```

预览窗口显示：
- 人体骨骼关键点连线（绿色）
- 状态：`READY` / `NOT_READY` / `LOST`
- 当前动作和原因
- 帧延迟（frame age）
- 按 Q 或 Esc 退出

## 四、完整系统联调

需要三个终端同时运行。

### 终端 1：启动 Go 服务

```bash
cd /home/julien/night

# 确保服务已构建
make build

# 启动服务
./bin/star-service -listen 127.0.0.1:50051 -db data/star.db

# 或直接运行
go run ./cmd/star-service -listen 127.0.0.1:50051 -db data/star.db
```

**预期输出**：
```
[INFO] Star service listening on 127.0.0.1:50051
[INFO] SQLite database: data/star.db
```

### 终端 2：启动识别运行时

```bash
cd /home/julien/night/recognizer

# 连接到 Go 服务（移除 --standalone）
.venv/bin/python -m star_recognizer run --config config.local.json

# 可选：无预览
.venv/bin/python -m star_recognizer run --config config.local.json --headless
```

**预期输出**：
```
Capture ready: {"width": 960, "height": 540, "requested_input": {"device": "Insta360 X5", "width": 1920, "height": 1080, "fps": 30, "codec": "mjpeg"}, "backend": "Windows DirectShow / FFmpeg stdout -> WSL"}
Waiting for UE or 'watch' to open a generation. No UE means no action output.
```

**此时 generation=0，不会输出动作事件**。

### 终端 3：模拟 UE 订阅（临时测试）

```bash
cd /home/julien/night/recognizer

# 模拟 UE 订阅 120 秒
.venv/bin/python -m star_recognizer watch --seconds 120
```

**预期输出**：
```
Temporary UE consumer generation=1727011234567890123; do not run alongside real UE.
{"generation":"1727011234567890123","state":"NOT_READY"}
{"generation":"1727011234567890123","state":"READY"}
```

**此时终端 2 会开始输出同样的 JSON 事件**。

在相机前做动作：
1. 站稳 0.6 秒 → `READY`
2. 蹲下 0.15 秒 → `SQUAT BEGIN`
3. 站起回到中央 0.25 秒 → `SQUAT COMPLETE`
4. 再次 `READY`

**重要**：
- `watch` 仅用于测试，不要和真实 UE 同时运行
- 新订阅会替换旧订阅
- 真实 UE 应调用 `WatchInput` gRPC 接口

## 五、视频回放测试

```bash
cd /home/julien/night/recognizer

# 使用录像测试（不会发送到 Go 服务）
.venv/bin/python -m star_recognizer run --standalone \
  --video /path/to/your/recording.mp4

# 必须是绝对路径
.venv/bin/python -m star_recognizer run --standalone \
  --video /home/julien/videos/demo.mp4
```

**用途**：
- 调试动作阈值
- 验证投影配置
- 离线开发（无需相机）

## 六、动作说明

### 准备姿势（Ready）

- 正面朝向相机
- 双脚并拢，直立站立
- 双臂自然下垂
- 保持 0.6 秒静止

### 六种动作

| 动作 | 英文 | 识别要点 | 配置阈值 |
|------|------|----------|----------|
| 蹲下 | `SQUAT` | 髋关节下降 14% 体高，膝盖 < 145° | `squat_drop` |
| 抬左腿 | `LEFT_LEG` | 左脚上升 12% 体高，右脚不动 | `leg_lift` |
| 抬右腿 | `RIGHT_LEG` | 右脚上升 12% 体高，左脚不动 | `leg_lift` |
| 向左跳 | `JUMP_LEFT` | 双脚腾空 + 向左位移 12% 体高 | `jump_distance` |
| 向右跳 | `JUMP_RIGHT` | 双脚腾空 + 向右位移 12% 体高 | `jump_distance` |
| 开合跳 | `JUMPING_JACK` | 双臂上举 + 双腿分开 70% 体高 | 无单独阈值 |

### 完成动作

每个动作必须**回到准备姿势**才算完成：
- 左右跳：必须跳回中央，不会识别反向跳
- 其他动作：回到直立站姿
- 回位需保持 0.25 秒

### 取消动作

以下情况自动取消当前动作：
- 人体丢失（`LOST`）
- 动作超时（15 秒）
- 无法识别的乱动（0.45 秒）
- UE 暂停/断开连接

## 七、阈值调优

如果动作误识别或识别不灵敏，修改 `config.local.json`：

```json
{
  "gestures": {
    "visibility": 0.6,           // 关键点可见度阈值 (0-1)
    "ready_ms": 600,             // 进入 Ready 需要的静止时长
    "candidate_ms": 150,         // 动作候选确认时长
    "return_ms": 250,            // 回位确认时长
    "unready_ms": 450,           // 丢失 Ready 的容忍时长
    "max_gap_ms": 600,           // 帧间隔超时 → Lost
    "action_timeout_ms": 15000,  // 动作未完成超时
    "center_tolerance": 0.12,    // 中央位置容差（体高比）
    "leg_lift": 0.12,            // 抬腿高度阈值
    "squat_drop": 0.14,          // 蹲下深度阈值
    "jump_rise": 0.035,          // 跳跃腾空高度阈值
    "jump_distance": 0.12        // 侧跳水平距离阈值
  }
}
```

**建议流程**：
1. 录制真实玩家视频
2. 使用 `--video` 回放测试
3. 逐步调整阈值
4. 验证多个玩家

## 八、故障排查

### Windows 端问题

#### FFmpeg 找不到设备
```
Error: cannot open 'video=Insta360 X5'
```

**检查**：
1. X5 是否在 Webcam 模式（不是充电模式）
2. 设备名称是否完全匹配（区分大小写）
3. 是否有其他程序占用相机

**解决**：
```bash
# 重新枚举设备
.venv/bin/python -m star_recognizer devices

# 复制准确的设备名到 config.local.json
```

#### FFmpeg 可执行文件不存在
```
FileNotFoundError: Windows FFmpeg not found: tools/windows-ffmpeg/ffmpeg.exe
```

**解决**：
```bash
# 下载 FFmpeg
.venv/bin/python scripts/fetch_windows_ffmpeg.py

# 或指定已有的 Windows FFmpeg
# 在 config.local.json 中设置：
"windows_ffmpeg": "/mnt/c/tools/ffmpeg/bin/ffmpeg.exe"
```

#### Windows interop 不可用
```
OSError: [Errno 8] Exec format error
```

**检查**：
```bash
# 测试能否执行 Windows 程序
/mnt/c/Windows/System32/cmd.exe /c ver

# 应输出 Windows 版本号
```

如果失败，检查 `/etc/wsl.conf`：
```ini
[interop]
enabled = true
appendWindowsPath = true
```

### WSL 端问题

#### MediaPipe 模型缺失
```
FileNotFoundError: missing model: models/pose_landmarker_lite.task
```

**解决**：
```bash
.venv/bin/python scripts/fetch_model.py
```

#### 依赖包缺失
```
ImportError: No module named 'mediapipe'
```

**解决**：
```bash
# 重新运行 setup
bash scripts/setup.sh

# 或手动安装
.venv/bin/pip install -r requirements.txt
```

#### 推理超时
```
RuntimeError: MediaPipe inference timed out
```

**原因**：
- CPU 负载过高
- 分辨率过高（2880×1440）
- 模型加载失败

**解决**：
1. 降低 output_width/output_height，保持 width/height 为设备支持的输入模式
2. 关闭其他 CPU 密集任务
3. 检查 `doctor` 输出的模型路径

### gRPC 连接问题

#### 无法连接 Go 服务
```
UNAVAILABLE: failed to connect to all addresses
```

**检查**：
```bash
# 1. Go 服务是否运行
ps aux | grep star-service

# 2. 端口是否监听
nc -zv 127.0.0.1 50051

# 3. 地址配置是否正确
grep address config.local.json
```

#### generation 冲突
```
FailedPrecondition: generation must exceed ...
```

**原因**：UE/watch 使用的 generation 小于等于上次的值

**解决**：
- `watch` 使用当前时间戳，通常不会冲突
- 真实 UE 每次暂停/恢复使用递增的 generation

### 性能问题

#### 帧延迟过高（> 200ms）
1. 检查 CPU 使用率
2. 降低相机分辨率
3. 关闭预览窗口（`--headless`）
4. 检查 Windows 系统负载

#### 大量丢帧（overwritten 计数高）
- 这是**正常的**：单槽缓冲设计允许丢帧
- 只要动作识别正常，无需处理
- 如果影响游戏，降低相机帧率

#### 动作延迟
- 调低 `candidate_ms`（但可能增加误触发）
- 检查 Go → UE 的网络延迟
- 确认 UE 及时处理 `InputEvent`

## 九、测试命令汇总

```bash
# 环境检查
.venv/bin/python -m star_recognizer doctor
.venv/bin/python -m star_recognizer doctor --go  # 额外测试 Go 连接

# 设备枚举
.venv/bin/python -m star_recognizer devices
.venv/bin/python -m star_recognizer devices --modes
.venv/bin/python -m star_recognizer probe

# 独立运行（仅 Python，无 Go）
.venv/bin/python -m star_recognizer run --standalone
.venv/bin/python -m star_recognizer run --standalone --headless
.venv/bin/python -m star_recognizer run --standalone --seconds 60

# 视频回放
.venv/bin/python -m star_recognizer run --standalone --video /path/to/video.mp4

# 连接 Go 服务
.venv/bin/python -m star_recognizer run
.venv/bin/python -m star_recognizer run --config config.local.json

# 模拟 UE 订阅
.venv/bin/python -m star_recognizer watch --seconds 120

# 单元测试
.venv/bin/python -m unittest discover -s tests -v
```

## 十、生产部署注意事项

1. **不要使用 `watch` 命令**：仅用于开发测试
2. **UE 集成**：调用 `WatchInput` gRPC 接口
3. **日志记录**：将 stderr 重定向到文件
4. **进程监控**：识别进程崩溃需要重启
5. **相机独占**：确保无其他程序使用 X5
6. **网络隔离**：服务仅监听 `127.0.0.1`
7. **优雅关闭**：捕获 SIGINT/SIGTERM，清理资源

## 相关文档

- [ARCHITECTURE.md](ARCHITECTURE.md) - 完整技术架构说明
- [README.md](README.md) - 项目概述和详细文档
- [proto/star/v1/star.proto](../proto/star/v1/star.proto) - gRPC 协议定义
- [docs/Go与Protobuf接入说明.md](../docs/Go与Protobuf接入说明.md) - Go 服务接入指南

# 向星而行 · MediaPipe 识别运行时

本轮实现独立 Python 识别进程。当前选择的运行方式：

```text
X5 USB → Windows FFmpeg / DirectShow → 原始视频管道 → WSL Python
                                                       ├─ MediaPipe Pose
                                                       ├─ 六动作互斥状态机
                                                       └─ gRPC → WSL Go → 后续 Windows UE
```

游戏不使用 HTML，不依赖 Android。Windows 仅启动一个 FFmpeg 采集程序，无需 Windows Python。WSL 直接启动并管理该子进程；画面只经过本机管道，不上传、不录制。另保留 Linux V4L2 相机和本地录像回放入口。

## 现有 WSL 环境

使用系统已有 Python，不重装 Go/CUDA。项目依赖独立放在本目录的 `.venv`。
目前采用 **MediaPipe CPU delegate**；已安装 CUDA 不等于 MediaPipe 自动使用 CUDA。后续 GPU 加速须独立验证，不能以此推断识别性能。

首次配置：

```bash
cd /home/julien/night/recognizer
bash scripts/setup.sh
.venv/bin/python scripts/fetch_windows_ffmpeg.py
.venv/bin/python -m star_recognizer devices
.venv/bin/python -m star_recognizer doctor
```

如已有安装依赖的虚拟环境，可直接用该环境的 Python，不需要重复执行 setup。依赖版本见 requirements.txt；协议生成额外依赖 requirements-dev.txt。模型来自 Google 版本化下载地址，FFmpeg 来自 ffmpeg.org 列出的 gyan.dev 构建，并校验发布方 SHA256。下载文件与虚拟环境不入 Git。

## X5 连接与配置

1. X5 用数据线连接 Windows，选择 Webcam 模式。
2. 关闭占用相机的 Windows 摄像头/会议软件，避免设备被占用。
3. `devices` 输出 DirectShow 设备名称。将准确名称写入 `config.local.json` 的 `camera.windows_device`。
4. 若需要自定义参数：`cp config.example.json config.local.json`。所有命令加 `--config config.local.json`。
5. `camera.windows_ffmpeg` 是从 WSL 可访问的 exe 路径，例如 `/mnt/c/tools/ffmpeg/bin/ffmpeg.exe`；默认使用本项目下载的便携版。

枚举某设备支持的分辨率/帧率（FFmpeg 枚举结束返回非零属正常行为）：

```bash
tools/windows-ffmpeg/ffmpeg.exe -hide_banner -list_options true -f dshow -i 'video=Insta360 X5'
```

默认申请 1280×720 / 30 FPS 普通视图，必须以设备实际支持的模式为准。如果选择 **2880×1440 全景输出**，将配置中的 width/height 改为相应值，并设置 `projection: "equirectangular"`；调整 yaw_deg、pitch_deg 和 horizontal_fov_deg，使玩家居中、头和双脚可见。全景需是已拼接的 2:1 经纬图，双鱼眼或上下双镜头画面不能直接使用。普通单镜头设 `projection: "perspective"`。

预览镜像仅改变显示，动作左右始终按玩家身体定义。相机固定，玩家正面朝向相机，保持足够空间；每次开局/恢复先在中央自然站稳。

若 WSL 无法执行 exe，检查 Windows interop 是否可用，例如 `/mnt/c/Windows/System32/cmd.exe /c ver`。若要改用已映射的 Linux 摄像头，将 backend 改为 v4l2，device 改为 `/dev/video0`；当前桥接方案不要求 USB/IP。

## 先独立验证人体识别

```bash
.venv/bin/python -m star_recognizer run --standalone
```

原生窗口显示关键点、Ready/NotReady/Lost、动作和连接状态；终端输出 JSON 动作事件。
按 Q/Esc 或 Ctrl+C 退出。没有桌面时加 `--headless`。
窗口显示的 frame age 是进入 WSL 后的处理时延，**不包含相机/Windows 内部缓冲**。

使用已有视频测试（不会发送给正式游戏）：

```bash
.venv/bin/python -m star_recognizer run --standalone --video /absolute/path/demo.mp4
```

六种动作：蹲下、抬左腿、抬右腿、向左跳、向右跳、开合跳。动作参数放在配置的 gestures 对象，具体字段及默认值见 GestureConfig。它们是初始调试值，须用真实玩家视频校准；当前没有宣称真实识别准确率。

## 接入现有 Go

终端一，启动现有服务：

```bash
cd /home/julien/night
go run ./cmd/star-service -listen 127.0.0.1:50051 -db data/star.db
```

终端二，启动识别端：

```bash
cd /home/julien/night/recognizer
.venv/bin/python -m star_recognizer run
```

终端三，在 UE 尚未接入时模拟一个输入订阅方：

```bash
cd /home/julien/night/recognizer
.venv/bin/python -m star_recognizer watch --seconds 120
```

`watch` 只调用 WatchInput，不调用 SaveRun，不自动发送模拟身体动作。不要和实际 UE 同时运行：新订阅会替换旧订阅。没有 UE/watch 时 generation=0，相机仍采集，但不输出动作。

协议使用仓库同一份 star.proto。运行顺序为 `Ready → Begin → Complete/Cancel → Ready`；丢人取消当前动作，回位后才可开始下一动作。左右跳回到中央才完成，回位不产生反向跳。暂停、重连、任务边界由 UE 通过新 generation 重置；本进程不决定玩法是否恢复。

采集帧进入处理链时绑定 generation 和进程内 reset epoch；旧回调不会修改新周期。视频队列保留最新帧，动作队列满则断开连接，不能丢弃 Complete 后继续。连接中断后清空消息，不重放身体动作。

## 测试

```bash
cd /home/julien/night/recognizer
.venv/bin/python -m unittest discover -s tests -v
```

测试区分合成骨骼状态机测试、真实 gRPC 传输测试及真实 MediaPipe 空白图推理。空白图推理只证明模型能运行及回调正确，不代替真人动作验收。相机实际模式、长期延迟、多人遮挡和六种动作阈值必须在目标设备验证。

参考：[MediaPipe Pose](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python)、[X5 Webcam](https://onlinemanual.insta360.com/x5/en-us/camera/appuse/obs)、[FFmpeg DirectShow](https://ffmpeg.org/ffmpeg-devices.html#dshow)。

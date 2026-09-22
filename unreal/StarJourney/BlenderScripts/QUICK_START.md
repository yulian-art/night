# Blender 建模脚本快速启动指南

## ✅ 脚本已就绪

您的 Blender 自动化建模脚本已生成完毕：

```
D:\UE\Projects\StarJourney\BlenderScripts\
├── wind_post_assets.py      (9.2 KB) - 风邮原野资产生成器
├── cloud_whale_assets.py    (11 KB)  - 云鲸星海资产生成器
├── GenerateAll.bat          (2.1 KB) - Windows 一键批量生成
└── README.md                (4.9 KB) - 完整使用文档
```

## 🚀 立即开始（3种方式）

### 方式 1: 一键批量生成（最简单）

双击运行：
```
D:\UE\Projects\StarJourney\BlenderScripts\GenerateAll.bat
```

脚本会自动：
- ✓ 检测 Blender 安装路径
- ✓ 生成风邮原野的 17 个资产
- ✓ 生成云鲸星海的 14 个资产
- ✓ 输出到正确的 UE Content 目录

### 方式 2: 命令行单独生成

```bash
# 风邮原野
blender --background --python wind_post_assets.py

# 云鲸星海
blender --background --python cloud_whale_assets.py
```

### 方式 3: Blender GUI 手动运行

1. 打开 Blender
2. Scripting 工作区
3. 打开 `.py` 脚本文件
4. 点击 Run Script

## 📦 将生成的资产

### 风邮原野 (17 个 FBX)

**环境 (8个):**
- ENV_GrassHill_01.fbx ~ 05.fbx (草地丘陵变体)
- ENV_MailPost_Station.fbx (邮驿驿站)
- ENV_WindPost.fbx (风信柱)

**障碍 (6个):**
- OBS_LowBranch_01.fbx ~ 03.fbx (低树枝 - 蹲下)
- OBS_RockStep_Left.fbx (石阶 - 抬左腿)
- OBS_RockStep_Right.fbx (石阶 - 抬右腿)
- OBS_Gap_Small.fbx (缺口 - 开合跳)

**装饰 (1个):**
- DEC_PaperCrane.fbx (纸鹤)

### 云鲸星海 (14 个 FBX)

**环境 (8个):**
- ENV_CloudPlatform_01.fbx ~ 05.fbx (云层平台变体)
- ENV_CloudWhale.fbx (云鲸主体)
- ENV_StarField_Background.fbx (星空背景)

**障碍 (4个):**
- OBS_CloudArch_Low.fbx (云拱门 - 蹲下)
- OBS_StarFragment_Left.fbx (星之碎片 - 抬左腿)
- OBS_StarFragment_Right.fbx (星之碎片 - 抬右腿)
- OBS_CloudGap.fbx (云层缺口 - 开合跳)

**装饰 (3个):**
- DEC_Star_Small.fbx (小星星)
- DEC_Aurora_Ribbon.fbx (极光带)
- DEC_Nebula_Cloud.fbx (星云团)

## 📐 资产设计特点

### 风邮原野特色

**草地丘陵 (5个变体):**
- 2000×2000 cm 平面
- 20×20 细分网格
- Voronoi 噪声位移 (50-150 强度)
- 10次平滑迭代

**邮驿驿站:**
- 300×300 cm 地基
- 4根立柱 (半径30, 高400)
- 锥形屋顶 (半径250, 高150)
- 所有部件合并为单一网格

**低树枝障碍 (3个变体):**
- 主枝半径15, 长400
- 横向放置 (高度150)
- 每个变体3-5根小树枝

### 云鲸星海特色

**云鲸主体:**
- 身体: 椭球 (500×200×160)
- 头部: 锥形 (半径120→40)
- 尾巴: 锥形 (半径100→0)
- 双鳍 + 背鳍
- Smooth Shading

**云层平台 (5个变体):**
- 2500×2500 cm 平面
- 25×25 细分网格
- Clouds 噪声位移 (80-230 强度)
- 15次平滑迭代

**星之碎片:**
- 主晶体: 锥形 (半径80)
- 3个细节晶体
- 旋转角度: 30°/45°

## 🔧 如果 Blender 不在 PATH 中

`GenerateAll.bat` 会按下面的顺序自动查找 Blender：

1. `BLENDER_PATH` 环境变量
2. 系统 PATH 中的 `blender.exe`
3. `%ProgramFiles%\Blender Foundation\*`
4. `D:\blender\blender.exe`

都没找到时，设置一次环境变量再重跑即可：

```batch
setx BLENDER_PATH "D:\blender\blender.exe"
```

注意两点：
- `BLENDER_PATH` 要指向 `blender.exe` 本体，而不是 `D:\blender` 这样的目录。
- 路径含空格也没问题，脚本内部已经处理好引号，不再依赖硬编码的安装路径。

## 📥 导入到 UE 的步骤

1. **运行生成脚本**（方式1/2/3任选）

2. **打开 UE Content Browser**
   - 导航到 `/Game/StarJourney/Models/WindPost/`
   - 导航到 `/Game/StarJourney/Models/CloudWhale/`

3. **拖拽 FBX 文件导入**
   - 或右键 -> Import to... 

4. **使用导入设置**：
   ```
   Auto Generate Collision: ✓
   Import Normals: Import Normals
   Import Uniform Scale: 1.0
   Convert Scene: ✓
   ```

5. **创建材质**（参考 SCENE_DESIGN.md）

6. **放置到测试关卡**

## 🎨 推荐工作流

### 今天（原型测试）

1. 运行 `GenerateAll.bat` 生成所有资产
2. 导入 ENV_GrassHill_01.fbx 和 OBS_LowBranch_01.fbx
3. 在 L_TestRunner 中测试碰撞和尺寸
4. 调整脚本参数（如果需要）

### 明天（完整场景）

1. 导入所有风邮原野资产
2. 创建材质（草地、木头、纸张）
3. 放置到完整关卡
4. 配置光照和后期处理

### 后天（第二关卡）

1. 导入云鲸星海资产
2. 创建材质（云雾、星光、晶体）
3. 设置粒子系统（星尘）
4. 动画化云鲸（可选）

## ⚡ 性能优化建议

生成后在 UE 中：

**LOD 设置**（大型资产）:
- GrassHill, CloudPlatform: 自动生成 LOD
- CloudWhale: 手动设置 3 级 LOD

**实例化**（重复资产）:
- 使用 Instanced Static Mesh Component
- 适用于: 纸鹤、星星、花朵

**材质优化**:
- 云雾: 半透明材质 + Noise
- 星光: Emissive + Additive Blend
- 草地: Subsurface Scattering

## 🐛 常见问题

**Q: 脚本运行后没有输出？**
- 检查 Blender 控制台是否有错误
- 确认输出目录是否可写
- 尝试手动创建目录

**Q: FBX 导入后模型是空的？**
- 检查 Scale 是否过大/过小
- 在 Blender 中检查模型是否生成
- 确认 FBX 文件大小 > 0 KB

**Q: 模型在 UE 中显示为黑色？**
- 需要创建材质
- 或临时使用 UE 默认材质

**Q: 碰撞不正确？**
- 在 UE 中右键资产 -> Edit
- Collision -> Auto Convex Collision

## 📝 下一步

1. **运行 GenerateAll.bat** 生成所有 31 个 FBX 文件
2. **导入到 UE** 并测试尺寸
3. **创建基础材质** 快速预览效果
4. **继续 C++ 开发** 集成动作识别系统

---

准备好了吗？双击运行 `GenerateAll.bat` 开始生成资产！🎨

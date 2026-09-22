# Blender 自动化建模脚本

## 📁 文件说明

- `wind_post_assets.py` - 风邮原野场景资产生成器
- `cloud_whale_assets.py` - 云鲸星海场景资产生成器

## 🚀 使用方法

### 方法 1: 命令行批量生成（推荐）

```bash
# 风邮原野资产
blender --background --python wind_post_assets.py

# 云鲸星海资产
blender --background --python cloud_whale_assets.py
```

**优点：** 无需打开 Blender GUI，自动批量生成所有资产

### 方法 2: Blender 内手动运行

1. 打开 Blender
2. 切换到 **Scripting** 工作区
3. 打开脚本文件（File -> Open）
4. 点击 **Run Script** 按钮

## 📦 输出目录

```
D:/UE/Projects/StarJourney/Content/StarJourney/Models/
├── WindPost/
│   ├── ENV/
│   │   ├── ENV_GrassHill_01.fbx ~ 05.fbx
│   │   ├── ENV_MailPost_Station.fbx
│   │   └── ENV_WindPost.fbx
│   ├── OBS/
│   │   ├── OBS_LowBranch_01.fbx ~ 03.fbx
│   │   ├── OBS_RockStep_Left.fbx
│   │   ├── OBS_RockStep_Right.fbx
│   │   └── OBS_Gap_Small.fbx
│   └── DEC/
│       └── DEC_PaperCrane.fbx
│
└── CloudWhale/
    ├── ENV/
    │   ├── ENV_CloudPlatform_01.fbx ~ 05.fbx
    │   ├── ENV_CloudWhale.fbx
    │   └── ENV_StarField_Background.fbx
    ├── OBS/
    │   ├── OBS_CloudArch_Low.fbx
    │   ├── OBS_StarFragment_Left.fbx
    │   ├── OBS_StarFragment_Right.fbx
    │   └── OBS_CloudGap.fbx
    └── DEC/
        ├── DEC_Star_Small.fbx
        ├── DEC_Aurora_Ribbon.fbx
        └── DEC_Nebula_Cloud.fbx
```

## 🎨 资产分类

### 风邮原野 (Wind Post)

**环境资产 (ENV):**
- `ENV_GrassHill_01~05` - 草地丘陵（5个变体，不同起伏）
- `ENV_MailPost_Station` - 邮驿驿站（4根立柱 + 锥形屋顶）
- `ENV_WindPost` - 风信柱（带箭头风向标和旗帜）

**障碍资产 (OBS):**
- `OBS_LowBranch_01~03` - 低树枝（需要蹲下，3个变体）
- `OBS_RockStep_Left/Right` - 石阶（需要抬左/右腿）
- `OBS_Gap_Small` - 小缺口标记（开合跳）

**装饰资产 (DEC):**
- `DEC_PaperCrane` - 纸鹤（可添加动画）

### 云鲸星海 (Cloud Whale)

**环境资产 (ENV):**
- `ENV_CloudPlatform_01~05` - 云层平台（5个变体，不同云雾效果）
- `ENV_CloudWhale` - 云鲸主体（身体 + 头 + 尾 + 鳍）
- `ENV_StarField_Background` - 星空背景球（反向法线）

**障碍资产 (OBS):**
- `OBS_CloudArch_Low` - 云拱门（需要蹲下）
- `OBS_StarFragment_Left/Right` - 星之碎片（需要抬左/右腿）
- `OBS_CloudGap` - 云层缺口（开合跳）

**装饰资产 (DEC):**
- `DEC_Star_Small` - 小星星
- `DEC_Aurora_Ribbon` - 极光带（曲线生成）
- `DEC_Nebula_Cloud` - 星云团（球体 + 噪声）

## ⚙️ FBX 导出设置

所有资产使用统一的 FBX 导出设置：

```
Transform:
  Scale: 1.0 (UE 使用 cm)
  Forward: -Y
  Up: Z
  Apply Transform: ✓

Geometry:
  Smoothing: Face
  Apply Modifiers: ✓
  
Armature:
  Primary Bone Axis: Y
  Secondary Bone Axis: X
```

## 🔧 自定义修改

### 调整尺寸

在脚本顶部修改 `EXPORT_SCALE`：

```python
EXPORT_SCALE = 1.0  # 默认 1:1
# EXPORT_SCALE = 0.01  # 如果 UE 中太大，缩小 100 倍
```

### 修改输出目录

```python
OUTPUT_DIR = Path("你的自定义路径")
```

### 生成单个资产

在 Python 控制台中调用单个函数：

```python
# 只生成邮驿驿站
create_mail_station()

# 只生成云鲸
create_cloud_whale()

# 生成特定变体的草地
create_grass_hill(variant=3)
```

## 📥 导入到 UE

1. 打开 UE Content Browser
2. 导航到对应目录
3. 拖拽 FBX 文件到 Content Browser
4. 使用以下导入设置：

```
Mesh:
  - Auto Generate Collision: ✓
  - Import Normals: Import Normals
  
Transform:
  - Import Uniform Scale: 1.0
  - Convert Scene: ✓
  
Material:
  - Import Materials: ✓
  - Import Textures: ✓
```

## ⚡ 性能提示

- 环境资产（草地、云层）使用了较多细分，可能需要在 UE 中设置 LOD
- 装饰资产（纸鹤、星星）建议使用 Instanced Static Mesh
- 背景球（星空）可以设置为 Skybox 材质

## 🐛 常见问题

**Q: Blender 找不到命令**

`GenerateAll.bat` 会自动查找 Blender（`BLENDER_PATH` 环境变量 -> 系统 PATH -> 常见安装目录），
一般不需要手动配置。若仍提示找不到，可设置环境变量：

```batch
setx BLENDER_PATH "D:\blender\blender.exe"
```

`BLENDER_PATH` 需指向 `blender.exe` 本体。也可以直接使用完整路径调用：

```bash
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python wind_post_assets.py
```

**Q: 输出目录不存在**
- 脚本会自动创建目录，无需手动创建

**Q: FBX 在 UE 中显示异常**
- 检查 Import Uniform Scale 是否为 1.0
- 检查 Forward/Up 轴是否正确（-Y Forward, Z Up）

**Q: 模型太大/太小**
- 修改脚本中的 `EXPORT_SCALE` 参数
- 或在 UE 导入时调整 Import Uniform Scale

## 📝 下一步

1. 运行脚本生成 FBX 文件
2. 导入到 UE
3. 在 UE 中创建材质（参考 `SCENE_DESIGN.md`）
4. 放置到测试关卡中
5. 调整碰撞和物理属性

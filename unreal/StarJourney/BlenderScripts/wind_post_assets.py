"""
Blender MCP 自动化脚本 - 风邮原野场景资产生成器
使用方法: blender --background --python wind_post_assets.py
"""

import bpy
import math
import os
from pathlib import Path

# ==================== 配置 ====================

OUTPUT_DIR = Path("D:/UE/Projects/StarJourney/Content/StarJourney/Models/WindPost")
EXPORT_SCALE = 1.0  # UE 使用 cm 为单位

# ==================== 工具函数 ====================

def clear_scene():
    """清空场景中的所有对象"""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def setup_units():
    """设置单位为厘米（匹配UE）"""
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 0.01

def export_fbx(obj_name, category="ENV"):
    """导出为 FBX"""
    filepath = OUTPUT_DIR / category / f"{obj_name}.fbx"
    filepath.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.object.select_all(action='DESELECT')
    bpy.data.objects[obj_name].select_set(True)

    bpy.ops.export_scene.fbx(
        filepath=str(filepath),
        use_selection=True,
        global_scale=EXPORT_SCALE,
        axis_forward='-Y',
        axis_up='Z',
        bake_space_transform=True,
        object_types={'MESH'},
        mesh_smooth_type='FACE',
        use_mesh_modifiers=True,
        use_armature_deform_only=True,
        add_leaf_bones=False,
        primary_bone_axis='Y',
        secondary_bone_axis='X',
    )
    print(f"✓ 已导出: {filepath}")

# ==================== 环境资产 ====================

def create_grass_hill(variant=1):
    """创建草地丘陵"""
    clear_scene()

    # 基础平面
    bpy.ops.mesh.primitive_plane_add(size=2000, location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = f"ENV_GrassHill_{variant:02d}"

    # 细分
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=20)
    bpy.ops.object.mode_set(mode='OBJECT')

    # 添加位移修改器
    mod_displace = obj.modifiers.new(name='Displace', type='DISPLACE')

    # 创建噪声纹理
    tex = bpy.data.textures.new(name='HillNoise', type='VORONOI')
    tex.noise_scale = 0.5 + variant * 0.1
    mod_displace.texture = tex
    mod_displace.strength = 50 + variant * 20
    mod_displace.mid_level = 0.5

    # 平滑
    mod_smooth = obj.modifiers.new(name='Smooth', type='SMOOTH')
    mod_smooth.iterations = 10

    export_fbx(obj.name, "ENV")

def create_mail_station():
    """创建邮驿驿站"""
    clear_scene()

    # 地基
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 50))
    base = bpy.context.active_object
    base.scale = (300, 300, 100)
    base.name = "Base"

    # 立柱们（4根）
    pillars = []
    for i, pos in enumerate([(-120, -120), (120, -120), (-120, 120), (120, 120)]):
        bpy.ops.mesh.primitive_cylinder_add(
            radius=30,
            depth=400,
            location=(pos[0], pos[1], 250)
        )
        pillar = bpy.context.active_object
        pillar.name = f"Pillar_{i+1}"
        pillars.append(pillar)

    # 屋顶
    bpy.ops.mesh.primitive_cone_add(
        radius1=250,
        radius2=0,
        depth=150,
        location=(0, 0, 500)
    )
    roof = bpy.context.active_object
    roof.name = "Roof"

    # 合并
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.join()
    base.name = "ENV_MailPost_Station"

    export_fbx(base.name, "ENV")

def create_wind_post():
    """创建风信柱"""
    clear_scene()

    # 主柱
    bpy.ops.mesh.primitive_cylinder_add(
        radius=10,
        depth=300,
        location=(0, 0, 150)
    )
    pole = bpy.context.active_object
    pole.name = "Pole"

    # 风向标（箭头）
    bpy.ops.mesh.primitive_cone_add(
        radius1=30,
        radius2=0,
        depth=60,
        location=(0, 0, 320)
    )
    arrow = bpy.context.active_object
    arrow.rotation_euler = (0, math.radians(90), 0)
    arrow.name = "Arrow"

    # 旗帜（平面）
    bpy.ops.mesh.primitive_plane_add(
        size=80,
        location=(0, -40, 280)
    )
    flag = bpy.context.active_object
    flag.scale = (1, 0.6, 1)
    flag.rotation_euler = (0, 0, 0)
    flag.name = "Flag"

    # 合并
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = pole
    bpy.ops.object.join()
    pole.name = "ENV_WindPost"

    export_fbx(pole.name, "ENV")

# ==================== 障碍资产 ====================

def create_low_branch(variant=1):
    """创建低树枝（需要蹲下）"""
    clear_scene()

    # 树枝主体
    bpy.ops.mesh.primitive_cylinder_add(
        radius=15,
        depth=400,
        location=(0, 0, 150)
    )
    branch = bpy.context.active_object
    branch.rotation_euler = (0, math.radians(90), 0)
    branch.name = f"OBS_LowBranch_{variant:02d}"

    # 添加细节（小树枝）
    for i in range(variant + 2):
        angle = (360 / (variant + 2)) * i
        x = 80 * math.cos(math.radians(angle))
        z = 150 + 40 * math.sin(math.radians(angle))

        bpy.ops.mesh.primitive_cylinder_add(
            radius=5,
            depth=80,
            location=(x, 0, z)
        )
        twig = bpy.context.active_object
        twig.rotation_euler = (0, math.radians(45), math.radians(angle))
        twig.name = f"Twig_{i+1}"

    # 合并
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = branch
    bpy.ops.object.join()

    export_fbx(branch.name, "OBS")

def create_rock_step(side='left'):
    """创建石阶（需要抬腿）"""
    clear_scene()

    y_offset = -100 if side == 'left' else 100

    # 基础石块
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, y_offset, 40))
    rock = bpy.context.active_object
    rock.scale = (120, 80, 80)
    rock.name = f"OBS_RockStep_{side.capitalize()}"

    # 添加细分和噪声使其不规则
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=3)
    bpy.ops.object.mode_set(mode='OBJECT')

    # 位移修改器
    mod_displace = rock.modifiers.new(name='Displace', type='DISPLACE')
    tex = bpy.data.textures.new(name='RockNoise', type='VORONOI')
    tex.noise_scale = 1.5
    mod_displace.texture = tex
    mod_displace.strength = 10

    export_fbx(rock.name, "OBS")

def create_small_gap():
    """创建小缺口标记（实际是空的，但需要导出占位符）"""
    clear_scene()

    # 创建边界标记（两个立柱）
    for x in [-150, 150]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, 50))
        marker = bpy.context.active_object
        marker.scale = (20, 20, 100)
        marker.name = f"GapMarker_{1 if x < 0 else 2}"

    # 合并
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = bpy.data.objects["GapMarker_1"]
    bpy.ops.object.join()
    bpy.context.active_object.name = "OBS_Gap_Small"

    export_fbx("OBS_Gap_Small", "OBS")

# ==================== 装饰资产 ====================

def create_paper_crane():
    """创建纸鹤"""
    clear_scene()

    # 身体
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    body = bpy.context.active_object
    body.scale = (30, 40, 20)
    body.name = "Body"

    # 头部
    bpy.ops.mesh.primitive_cone_add(
        radius1=15,
        radius2=5,
        depth=25,
        location=(0, 25, 0)
    )
    head = bpy.context.active_object
    head.rotation_euler = (math.radians(90), 0, 0)
    head.name = "Head"

    # 翅膀（左）
    bpy.ops.mesh.primitive_plane_add(size=1, location=(-30, 0, 5))
    wing_l = bpy.context.active_object
    wing_l.scale = (40, 50, 1)
    wing_l.rotation_euler = (0, 0, math.radians(-30))
    wing_l.name = "Wing_L"

    # 翅膀（右）
    bpy.ops.mesh.primitive_plane_add(size=1, location=(30, 0, 5))
    wing_r = bpy.context.active_object
    wing_r.scale = (40, 50, 1)
    wing_r.rotation_euler = (0, 0, math.radians(30))
    wing_r.name = "Wing_R"

    # 尾巴
    bpy.ops.mesh.primitive_cone_add(
        radius1=10,
        radius2=2,
        depth=35,
        location=(0, -30, 0)
    )
    tail = bpy.context.active_object
    tail.rotation_euler = (math.radians(-90), 0, 0)
    tail.name = "Tail"

    # 合并
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    body.name = "DEC_PaperCrane"

    export_fbx(body.name, "DEC")

# ==================== 批量生成 ====================

def generate_all_assets():
    """生成所有资产"""
    setup_units()

    print("\n========== 开始生成风邮原野资产 ==========\n")

    # 环境资产
    print("生成环境资产...")
    for i in range(1, 6):
        create_grass_hill(i)
    create_mail_station()
    create_wind_post()

    # 障碍资产
    print("\n生成障碍资产...")
    for i in range(1, 4):
        create_low_branch(i)
    create_rock_step('left')
    create_rock_step('right')
    create_small_gap()

    # 装饰资产
    print("\n生成装饰资产...")
    create_paper_crane()

    print("\n========== 所有资产生成完成！ ==========")
    print(f"输出目录: {OUTPUT_DIR}")

# ==================== 主入口 ====================

if __name__ == "__main__":
    generate_all_assets()

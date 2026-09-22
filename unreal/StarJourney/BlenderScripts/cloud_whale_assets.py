"""
Blender MCP 自动化脚本 - 云鲸星海场景资产生成器
使用方法: blender --background --python cloud_whale_assets.py
"""

import bpy
import math
import os
from pathlib import Path

# ==================== 配置 ====================

OUTPUT_DIR = Path("D:/UE/Projects/StarJourney/Content/StarJourney/Models/CloudWhale")
EXPORT_SCALE = 1.0

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

def create_cloud_platform(variant=1):
    """创建云层平台"""
    clear_scene()

    # 基础平面
    bpy.ops.mesh.primitive_plane_add(size=2500, location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = f"ENV_CloudPlatform_{variant:02d}"

    # 细分
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=25)
    bpy.ops.object.mode_set(mode='OBJECT')

    # 添加位移修改器（云层起伏）
    mod_displace = obj.modifiers.new(name='Displace', type='DISPLACE')
    tex = bpy.data.textures.new(name='CloudNoise', type='CLOUDS')
    tex.noise_scale = 0.8 + variant * 0.15
    tex.noise_depth = 4
    mod_displace.texture = tex
    mod_displace.strength = 80 + variant * 30
    mod_displace.mid_level = 0.6

    # 平滑
    mod_smooth = obj.modifiers.new(name='Smooth', type='SMOOTH')
    mod_smooth.iterations = 15

    export_fbx(obj.name, "ENV")

def create_cloud_whale():
    """创建云鲸主体"""
    clear_scene()

    # 身体（椭球体）
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=200,
        location=(0, 0, 0),
        segments=32,
        ring_count=16
    )
    body = bpy.context.active_object
    body.scale = (2.5, 1.0, 0.8)  # 拉长
    body.name = "Body"

    # 头部（圆锥）
    bpy.ops.mesh.primitive_cone_add(
        radius1=120,
        radius2=40,
        depth=250,
        location=(380, 0, 0)
    )
    head = bpy.context.active_object
    head.rotation_euler = (0, math.radians(90), 0)
    head.name = "Head"

    # 尾巴（圆锥）
    bpy.ops.mesh.primitive_cone_add(
        radius1=100,
        radius2=0,
        depth=300,
        location=(-450, 0, 0)
    )
    tail = bpy.context.active_object
    tail.rotation_euler = (0, math.radians(-90), 0)
    tail.name = "Tail"

    # 左鳍
    bpy.ops.mesh.primitive_plane_add(size=1, location=(-80, -150, 0))
    fin_l = bpy.context.active_object
    fin_l.scale = (180, 100, 1)
    fin_l.rotation_euler = (0, math.radians(-20), math.radians(-30))
    fin_l.name = "Fin_L"

    # 右鳍
    bpy.ops.mesh.primitive_plane_add(size=1, location=(-80, 150, 0))
    fin_r = bpy.context.active_object
    fin_r.scale = (180, 100, 1)
    fin_r.rotation_euler = (0, math.radians(20), math.radians(30))
    fin_r.name = "Fin_R"

    # 背鳍
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 120))
    dorsal = bpy.context.active_object
    dorsal.scale = (200, 80, 1)
    dorsal.rotation_euler = (math.radians(90), 0, 0)
    dorsal.name = "Dorsal"

    # 合并
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    body.name = "ENV_CloudWhale"

    # 平滑着色
    bpy.ops.object.shade_smooth()

    export_fbx(body.name, "ENV")

def create_star_field_background():
    """创建星空背景球"""
    clear_scene()

    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=10000,
        location=(0, 0, 0),
        segments=64,
        ring_count=32
    )
    sphere = bpy.context.active_object
    sphere.name = "ENV_StarField_Background"

    # 反转法线（从内部观看）
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.flip_normals()
    bpy.ops.object.mode_set(mode='OBJECT')

    export_fbx(sphere.name, "ENV")

# ==================== 障碍资产 ====================

def create_cloud_arch():
    """创建云拱门（需要蹲下）"""
    clear_scene()

    # 左柱
    bpy.ops.mesh.primitive_cylinder_add(
        radius=60,
        depth=250,
        location=(-150, 0, 125)
    )
    left_pillar = bpy.context.active_object
    left_pillar.name = "LeftPillar"

    # 右柱
    bpy.ops.mesh.primitive_cylinder_add(
        radius=60,
        depth=250,
        location=(150, 0, 125)
    )
    right_pillar = bpy.context.active_object
    right_pillar.name = "RightPillar"

    # 横梁
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 180))
    beam = bpy.context.active_object
    beam.scale = (300, 80, 40)
    beam.name = "Beam"

    # 合并
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = left_pillar
    bpy.ops.object.join()
    left_pillar.name = "OBS_CloudArch_Low"

    # 添加云雾效果（位移）
    mod_displace = left_pillar.modifiers.new(name='Displace', type='DISPLACE')
    tex = bpy.data.textures.new(name='CloudTexture', type='CLOUDS')
    tex.noise_scale = 1.2
    mod_displace.texture = tex
    mod_displace.strength = 15

    export_fbx(left_pillar.name, "OBS")

def create_star_fragment(side='left'):
    """创建星之碎片（需要抬腿）"""
    clear_scene()

    y_offset = -100 if side == 'left' else 100

    # 主体（尖锐的晶体）
    bpy.ops.mesh.primitive_cone_add(
        radius1=80,
        radius2=20,
        depth=120,
        location=(0, y_offset, 60)
    )
    fragment = bpy.context.active_object
    fragment.rotation_euler = (math.radians(30), 0, math.radians(45))
    fragment.name = f"OBS_StarFragment_{side.capitalize()}"

    # 添加细节晶体
    for i in range(3):
        angle = 120 * i
        x_off = 40 * math.cos(math.radians(angle))
        z_off = 40 * math.sin(math.radians(angle))

        bpy.ops.mesh.primitive_cone_add(
            radius1=15,
            radius2=5,
            depth=50,
            location=(x_off, y_offset, 60 + z_off)
        )
        detail = bpy.context.active_object
        detail.rotation_euler = (math.radians(angle), 0, 0)
        detail.name = f"Crystal_{i+1}"

    # 合并
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = fragment
    bpy.ops.object.join()

    export_fbx(fragment.name, "OBS")

def create_cloud_gap():
    """创建云层缺口（开合跳）"""
    clear_scene()

    # 左云块
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-200, 0, 0))
    left = bpy.context.active_object
    left.scale = (150, 200, 50)
    left.name = "LeftCloud"

    # 右云块
    bpy.ops.mesh.primitive_cube_add(size=1, location=(200, 0, 0))
    right = bpy.context.active_object
    right.scale = (150, 200, 50)
    right.name = "RightCloud"

    # 添加云雾效果
    for obj in [left, right]:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        mod_displace = obj.modifiers.new(name='Displace', type='DISPLACE')
        tex = bpy.data.textures.new(name=f'Cloud_{obj.name}', type='CLOUDS')
        tex.noise_scale = 1.0
        mod_displace.texture = tex
        mod_displace.strength = 20

        obj.select_set(False)

    # 合并
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = left
    bpy.ops.object.join()
    left.name = "OBS_CloudGap"

    export_fbx(left.name, "OBS")

# ==================== 装饰资产 ====================

def create_small_star():
    """创建小星星"""
    clear_scene()

    # 五角星形状（用圆锥近似）
    bpy.ops.mesh.primitive_cone_add(
        radius1=15,
        radius2=0,
        depth=30,
        location=(0, 0, 0)
    )
    star = bpy.context.active_object
    star.name = "DEC_Star_Small"

    export_fbx(star.name, "DEC")

def create_aurora_ribbon():
    """创建极光带"""
    clear_scene()

    # 曲线路径
    bpy.ops.curve.primitive_nurbs_path_add(location=(0, 0, 0))
    curve = bpy.context.active_object
    curve.name = "AuroraPath"

    # 拉伸曲线
    curve.data.bevel_depth = 50
    curve.data.bevel_resolution = 4
    curve.scale = (500, 300, 200)

    # 转换为网格
    bpy.ops.object.convert(target='MESH')
    curve.name = "DEC_Aurora_Ribbon"

    export_fbx(curve.name, "DEC")

def create_nebula_cloud():
    """创建星云团"""
    clear_scene()

    # 基础球体
    bpy.ops.mesh.primitive_ico_sphere_add(
        radius=180,
        subdivisions=3,
        location=(0, 0, 0)
    )
    nebula = bpy.context.active_object
    nebula.name = "DEC_Nebula_Cloud"

    # 添加位移使其不规则
    mod_displace = nebula.modifiers.new(name='Displace', type='DISPLACE')
    tex = bpy.data.textures.new(name='NebulaNoise', type='CLOUDS')
    tex.noise_scale = 0.6
    tex.noise_depth = 6
    mod_displace.texture = tex
    mod_displace.strength = 40

    export_fbx(nebula.name, "DEC")

# ==================== 批量生成 ====================

def generate_all_assets():
    """生成所有资产"""
    setup_units()

    print("\n========== 开始生成云鲸星海资产 ==========\n")

    # 环境资产
    print("生成环境资产...")
    for i in range(1, 6):
        create_cloud_platform(i)
    create_cloud_whale()
    create_star_field_background()

    # 障碍资产
    print("\n生成障碍资产...")
    create_cloud_arch()
    create_star_fragment('left')
    create_star_fragment('right')
    create_cloud_gap()

    # 装饰资产
    print("\n生成装饰资产...")
    create_small_star()
    create_aurora_ribbon()
    create_nebula_cloud()

    print("\n========== 所有资产生成完成！ ==========")
    print(f"输出目录: {OUTPUT_DIR}")

# ==================== 主入口 ====================

if __name__ == "__main__":
    generate_all_assets()

#!/usr/bin/env python3
"""云鲸星海（第 3 关）四件障碍物 —— 唯一权威生成脚本。

取代此前 13 个 agent 并发留下的 4 套互相冲突的实现（12 个脚本、2 个孤儿库）。
本脚本自包含：不 import 任何 art/blender 下的其它模块。

## 世界约定（与角色管线一致）
- Blender 1 单位 = 1 米，Z 轴向上；**玩家沿 +X 跑**，横向（换道方向）为 Y。
- 导出 FBX 用 `global_scale=100`（使文件本身为厘米制，UE 导入缩放保持 1.0）。
  `axis_forward='-Z'` / `axis_up='Y'` 是 Blender 的 FBX 默认值（标准 FBX 惯例）。
  实测确认：`global_scale` 与 `apply_scale_options` 的取值无关，三种取值均得到 ×100。
- 导出 GLB 为米制 1:1（便于在 Blender 里复检）。

## 规格
| 资产 | 规格 |
|---|---|
| `OBS_CloudArch_Low` | 2 圆柱立柱 + 1 横梁 + 云团；**横梁沿 Y 跨路**；净空 **1.66 m**；总高 **2.56 m** |
| `OBS_StarFragment_Left/_Right` | 主晶体 + **3 个细节小晶体** + 基座；高 **2.50 m**；两侧几何完全相同，仅差 ±1.0 m 的 Y 偏移 |
| `OBS_CloudGap` | 两块云台 3(X)×8(Y)×1(Z)，**沿 X 留 1.0 m 缺口**（玩家开合跳越过） |

**净空口径说明**：角色高 1.80 m。若净空取 2.56 m，站着即可通过、蹲下形同虚设；
故取「**总高 2.56 / 净空 1.66**」，使蹲下成为物理必需。

运行：blender --background --python art/blender/obstacles/build_all_obstacles.py
"""

import hashlib
import json
import math
import os
import sys

import bpy
from mathutils import Vector

# --------------------------------------------------------------------------
# 常量
# --------------------------------------------------------------------------

REPO = "/Users/imac/南客松-v2/night"
EXPORT_DIR = os.path.join(REPO, "art", "export", "obstacles")
PREVIEW_DIR = os.path.join(REPO, "art", "export", "previews")

#: 字符身高，用于净空口径的合理性检查
HERO_HEIGHT = 1.80

#: 云拱门：总高 2.56、净空 1.66（角色 1.80 必须蹲下）
ARCH_TOTAL_HEIGHT = 2.56
ARCH_CLEARANCE = 1.66
ARCH_SPAN_Y = 3.0      # 立柱中心 |Y|
ARCH_PILLAR_R = 0.32
ARCH_DEPTH_X = 0.60    # 拱门沿跑动方向的半厚
ARCH_MAX_TRIS = 2500

#: 星之碎片
STAR_HEIGHT = 2.50
STAR_MAX_TRIS = 2000
#: 左右偏移。角色面向 +X 时其左手方向为 +Y，故 Left=+1.0。
#: 设计文档要求「左右按玩家身体定义」，最终须在实机用真人抬左腿确认；
#: 若反了，只改这两个常量，不要动几何。
LEFT_Y_OFFSET = 1.0
RIGHT_Y_OFFSET = -1.0

#: 云层缺口：两块 3(X)×8(Y)×1(Z)，沿 X 留 1.0 m 缺口
GAP_BLOCK_X = 3.0
GAP_BLOCK_Y = 8.0
GAP_BLOCK_Z = 1.0
GAP_WIDTH = 1.0
GAP_MAX_TRIS = 2500

#: 云噪声位移（四件共用，保证观感一致）
CLOUD_NOISE_SCALE = 0.62
CLOUD_NOISE_STRENGTH = 0.13

#: 第 3 关色板 —— 严格取自参考图（白大理石 + 暖金 + 青碧玻璃 + 星光白）。
#: 参考图里云是**脚下的云海**，不是构件材质；构件本身是古典白石建筑配金饰。
MATERIALS = {
    "M_OBS_Marble":    dict(base=(0.93, 0.92, 0.89, 1.0), rough=0.35, emit=None, power=0.0),
    "M_OBS_MarbleWarm":dict(base=(0.86, 0.82, 0.76, 1.0), rough=0.55, emit=None, power=0.0),
    "M_OBS_Gold":      dict(base=(0.83, 0.68, 0.34, 1.0), rough=0.25, emit=None, power=0.0, metal=0.90),
    "M_OBS_Aqua":      dict(base=(0.55, 0.85, 0.85, 1.0), rough=0.12, emit=(0.45, 0.85, 0.88), power=1.2),
    "M_OBS_StarWhite": dict(base=(1.00, 0.98, 0.93, 1.0), rough=0.20, emit=(1.00, 0.96, 0.85), power=3.0),
    "M_OBS_Banner":    dict(base=(0.22, 0.28, 0.52, 1.0), rough=0.70, emit=None, power=0.0),
    "M_OBS_CloudSea":  dict(base=(0.88, 0.90, 0.96, 1.0), rough=0.90, emit=None, power=0.0),
}


def log(msg):
    print(f"[obstacles] {msg}", flush=True)


def fail(msg):
    print(f"[obstacles] FAIL: {msg}", file=sys.stderr, flush=True)
    raise SystemExit(1)


# --------------------------------------------------------------------------
# 场景与材质
# --------------------------------------------------------------------------

def reset_scene():
    """清场。必须用数据 API：bpy.ops.object.delete 在上下文不满足时会静默失败。"""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras,
                 bpy.data.lights, bpy.data.textures, bpy.data.images):
        for block in list(coll):
            if block.users == 0:
                try:
                    coll.remove(block)
                except Exception:
                    pass


def material(name):
    """按冻结色板取材质（已存在则复用，保证四件共用同一份）。"""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    spec = MATERIALS[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = spec["base"]
    bsdf.inputs["Roughness"].default_value = spec["rough"]
    bsdf.inputs["Metallic"].default_value = spec.get("metal", 0.0)
    if spec["emit"]:
        bsdf.inputs["Emission Color"].default_value = (*spec["emit"], 1.0)
        bsdf.inputs["Emission Strength"].default_value = spec["power"]
    return mat


def assign(obj, *names):
    obj.data.materials.clear()
    for n in names:
        obj.data.materials.append(material(n))


# --------------------------------------------------------------------------
# 几何工具
# --------------------------------------------------------------------------

def activate(obj):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def apply_modifiers(obj):
    """用 depsgraph 求值替换网格：headless 下比 bpy.ops.object.modifier_apply 稳。"""
    deps = bpy.context.evaluated_depsgraph_get()
    baked = bpy.data.meshes.new_from_object(obj.evaluated_get(deps))
    old = obj.data
    obj.modifiers.clear()
    obj.data = baked
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return obj


def subdivide(obj, cuts):
    m = obj.modifiers.new("sub", "SUBSURF")
    m.subdivision_type = "SIMPLE"
    m.levels = cuts
    m.render_levels = cuts
    return apply_modifiers(obj)


def cloud_noise(obj, strength=None, scale=None):
    tex = bpy.data.textures.new(f"cloud_{obj.name}", type="CLOUDS")
    tex.noise_scale = scale if scale is not None else CLOUD_NOISE_SCALE
    m = obj.modifiers.new("disp", "DISPLACE")
    m.texture = tex
    m.strength = strength if strength is not None else CLOUD_NOISE_STRENGTH
    m.mid_level = 0.5
    return apply_modifiers(obj)


def join(objs, name):
    for o in bpy.data.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    merged = bpy.context.view_layer.objects.active
    merged.name = name
    merged.data.name = name
    return merged


def cube(name, x, y, z, loc=(0, 0, 0), rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = (x, y, z)
    return o


def cylinder(name, radius, depth, loc, verts=16):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, vertices=verts, location=loc)
    o = bpy.context.active_object
    o.name = name
    return o


def cone(name, r1, r2, depth, loc, verts=12, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(radius1=r1, radius2=r2, depth=depth,
                                    vertices=verts, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    return o


def ico(name, radius, loc, subdiv=2):
    bpy.ops.mesh.primitive_ico_sphere_add(radius=radius, subdivisions=subdiv, location=loc)
    o = bpy.context.active_object
    o.name = name
    return o


def smooth(obj, on=True):
    for p in obj.data.polygons:
        p.use_smooth = on


def flat(obj):
    smooth(obj, False)


def bounds(objs):
    bpy.context.view_layer.update()   # bound_box 是缓存值，改过网格后必须刷新
    pts = []
    for o in objs:
        if o.type != "MESH":
            continue
        pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    if not pts:
        return None
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    return dict(
        size=(round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3), round(max(zs) - min(zs), 3)),
        x=(round(min(xs), 3), round(max(xs), 3)),
        y=(round(min(ys), 3), round(max(ys), 3)),
        z=(round(min(zs), 3), round(max(zs), 3)),
    )


def tri_count(objs):
    n = 0
    for o in objs:
        if o.type == "MESH":
            o.data.calc_loop_triangles()
            n += len(o.data.loop_triangles)
    return n


def vertex_hash(obj):
    """局部坐标哈希，用于证明左右两件几何完全相同。"""
    h = hashlib.sha256()
    for v in obj.data.vertices:
        h.update(f"{v.co.x:.6f},{v.co.y:.6f},{v.co.z:.6f};".encode())
    return h.hexdigest()[:16]


def drop_to_ground(objs):
    """整体贴地：把最低点抬到 Z=0（位移与噪声之后必做）。"""
    b = bounds(objs)
    if b and abs(b["z"][0]) > 1e-6:
        for o in objs:
            o.location.z -= b["z"][0]
        for o in objs:
            activate(o)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return bounds(objs)


def export(objs, name):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    for o in bpy.data.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]

    fbx = os.path.join(EXPORT_DIR, f"{name}.fbx")
    glb = os.path.join(EXPORT_DIR, f"{name}.glb")
    # use_mesh_modifiers 是 Blender 5.1 的合法参数（没有 apply_modifiers）
    bpy.ops.export_scene.fbx(
        filepath=fbx, use_selection=True,
        global_scale=100.0, apply_scale_options="FBX_SCALE_ALL",
        axis_forward="-Z", axis_up="Y",
        use_mesh_modifiers=True, object_types={"MESH"},
    )
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True)
    for p in (fbx, glb):
        if not os.path.exists(p) or os.path.getsize(p) < 200:
            fail(f"导出文件缺失或过小: {p}")
    return fbx, glb


def preview(name, objs, out):
    """出一张 3/4 视角预览图，便于人眼确认。"""
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    # 只渲染本件：否则同场景里的兄弟物体会混进画面（例如左右碎片互相入镜）
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = o not in objs
    b = bounds(objs)
    ctr = Vector(((b["x"][0] + b["x"][1]) / 2, (b["y"][0] + b["y"][1]) / 2, (b["z"][0] + b["z"][1]) / 2))
    size = max(b["size"])

    cam_data = bpy.data.cameras.new("preview_cam")
    cam = bpy.data.objects.new("preview_cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = ctr + Vector((size * 1.15, -size * 1.35, size * 0.45))
    cam.rotation_euler = (ctr - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam

    sun = bpy.data.lights.new("preview_sun", "SUN")
    # 2.4 而非 4.5：太亮会把深蓝紫洗成近白，看不出材质色
    sun.energy = 2.4
    so = bpy.data.objects.new("preview_sun", sun)
    bpy.context.scene.collection.objects.link(so)
    so.rotation_euler = (math.radians(56), 0, math.radians(35))

    world = bpy.data.worlds.new("preview_world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.04, 0.055, 0.10, 1.0)
    bpy.context.scene.world = world

    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = 700
    sc.render.resolution_y = 700
    path = os.path.join(PREVIEW_DIR, f"{out}.png")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)

    for o in (cam, so):
        bpy.data.objects.remove(o, do_unlink=True)
    return path


# --------------------------------------------------------------------------
# 资产 1：云拱门（横梁沿 Y 跨路，净空 1.66，总高 2.56）
# --------------------------------------------------------------------------

def build_cloud_arch(report):
    reset_scene()
    parts = []

    # ---- 古典白石拱门（对照参考图：柱础 + 柱身 + 柱头 + 金色线脚 + 三角旗）----
    # 关键取舍：**开口下沿在整条走廊上恒为 1.66**（玩法尺寸不许被造型动到），
    # 拱券只做在过梁**上方**作为装饰冠，因此净空精确且不受弧线影响。
    lintel_h = 0.30
    lintel_top = ARCH_CLEARANCE + lintel_h          # 1.96
    crown_t = 0.34
    # 冠顶中心线过 (±3.0, lintel_top+crown_t/2) 与 (0, ARCH_TOTAL_HEIGHT-crown_t/2)
    zc, R = -15.05, 17.44

    # 柱础（大理石）+ 柱身 + 金色柱头，立在三条车道之外（|Y| = 3.0）
    for side, y in (("L", ARCH_SPAN_Y), ("R", -ARCH_SPAN_Y)):
        plinth = cube(f"plinth_{side}", 0.78, 0.78, 0.14, loc=(0.0, y, 0.07))
        activate(plinth)
        bpy.ops.object.transform_apply(scale=True)
        flat(plinth)
        assign(plinth, "M_OBS_MarbleWarm")
        parts.append(plinth)

        shaft = cube(f"shaft_{side}", 0.46, 0.46, ARCH_CLEARANCE - 0.14,
                     loc=(0.0, y, 0.14 + (ARCH_CLEARANCE - 0.14) / 2.0))
        activate(shaft)
        bpy.ops.object.transform_apply(scale=True)
        flat(shaft)
        assign(shaft, "M_OBS_Marble")
        parts.append(shaft)

        cap = cube(f"capital_{side}", 0.62, 0.62, 0.12, loc=(0.0, y, ARCH_CLEARANCE - 0.06))
        activate(cap)
        bpy.ops.object.transform_apply(scale=True)
        flat(cap)
        assign(cap, "M_OBS_Gold")
        parts.append(cap)

    # 过梁：下沿正好 1.66，横跨整条路
    lintel = cube("lintel", ARCH_DEPTH_X * 2, ARCH_SPAN_Y * 2 + 0.62, lintel_h,
                  loc=(0.0, 0.0, ARCH_CLEARANCE + lintel_h / 2.0))
    activate(lintel)
    bpy.ops.object.transform_apply(scale=True)
    subdivide(lintel, 2)
    flat(lintel)
    assign(lintel, "M_OBS_Marble")
    parts.append(lintel)

    # 过梁顶面的金色线脚
    fillet = cube("fillet", ARCH_DEPTH_X * 2 + 0.06, ARCH_SPAN_Y * 2 + 0.68, 0.05,
                  loc=(0.0, 0.0, lintel_top + 0.025))
    activate(fillet)
    bpy.ops.object.transform_apply(scale=True)
    flat(fillet)
    assign(fillet, "M_OBS_Gold")
    parts.append(fillet)

    # 装饰拱冠：沿圆弧排布的石块（在过梁之上，不影响净空）
    N = 11
    seg_len = (2 * ARCH_SPAN_Y / N) * 1.08
    for i in range(N):
        y0 = -ARCH_SPAN_Y + (i + 0.5) * (2 * ARCH_SPAN_Y / N)
        z0 = zc + math.sqrt(R * R - y0 * y0)
        slope = -y0 / math.sqrt(R * R - y0 * y0)
        seg = cube(f"crown_{i}", ARCH_DEPTH_X * 2, seg_len, crown_t,
                   loc=(0.0, y0, z0))
        activate(seg)
        bpy.ops.object.transform_apply(scale=True)
        seg.rotation_euler = (math.atan(slope), 0.0, 0.0)
        flat(seg)
        # 单数块用暖色石，读出砌块感
        assign(seg, "M_OBS_Marble" if i % 2 == 0 else "M_OBS_MarbleWarm")
        parts.append(seg)

    # 冠顶两端各一颗星白宝顶
    for side, y in (("L", ARCH_SPAN_Y * 0.62), ("R", -ARCH_SPAN_Y * 0.62)):
        z0 = zc + math.sqrt(R * R - y * y)
        fin = ico(f"finial_{side}", 0.10, (0.0, y, z0 + crown_t / 2 + 0.07), subdiv=1)
        smooth(fin)
        assign(fin, "M_OBS_StarWhite")
        parts.append(fin)

    # 三角旗：挂在柱内侧，**必须落在走廊之外**（|Y| >= 2.70），否则会吃掉净空
    for side, y in (("L", ARCH_SPAN_Y - 0.15), ("R", -(ARCH_SPAN_Y - 0.15))):
        flag = cube(f"banner_{side}", 0.04, 0.30, 0.62,
                    loc=(ARCH_DEPTH_X + 0.03, y, ARCH_CLEARANCE - 0.34))
        activate(flag)
        bpy.ops.object.transform_apply(scale=True)
        flat(flag)
        assign(flag, "M_OBS_Banner")
        parts.append(flag)

        star = cube(f"emblem_{side}", 0.03, 0.11, 0.11,
                    loc=(ARCH_DEPTH_X + 0.06, y, ARCH_CLEARANCE - 0.26),
                    rot=(0.0, math.radians(45.0), 0.0))
        activate(star)
        bpy.ops.object.transform_apply(scale=True)
        flat(star)
        assign(star, "M_OBS_Gold")
        parts.append(star)

    arch = join(parts, "OBS_CloudArch_Low")

    # ---- 自检 ----
    b = drop_to_ground([arch])
    corridor = [arch.matrix_world @ v.co for v in arch.data.vertices
                if abs((arch.matrix_world @ v.co).y) < ARCH_SPAN_Y - ARCH_PILLAR_R - 0.1]
    clearance = min((p.z for p in corridor), default=None)
    tris = tri_count([arch])

    if clearance is None or abs(clearance - ARCH_CLEARANCE) > 0.05:
        fail(f"拱门净空 {clearance} != {ARCH_CLEARANCE}")
    if abs(b["size"][2] - ARCH_TOTAL_HEIGHT) > 0.08:
        fail(f"拱门总高 {b['size'][2]} != {ARCH_TOTAL_HEIGHT}")
    if b["size"][1] < 2 * ARCH_SPAN_Y:
        fail(f"拱门 Y 跨距 {b['size'][1]} 不足（横梁没跨路）")
    if tris > ARCH_MAX_TRIS:
        fail(f"拱门面数 {tris} > {ARCH_MAX_TRIS}")

    report["OBS_CloudArch_Low"] = dict(
        size=b["size"], y=b["y"], z=b["z"], tris=tris,
        clearance=round(clearance, 3), hero_height=HERO_HEIGHT,
        crouch_required=clearance < HERO_HEIGHT,
    )
    export([arch], "OBS_CloudArch_Low")
    preview("OBS_CloudArch_Low", [arch], "OBS_CloudArch_Low")


# --------------------------------------------------------------------------
# 资产 2：星之碎片（主晶体 + 3 细节晶体 + 基座；左右仅差 ±1 m）
# --------------------------------------------------------------------------

def build_star_fragment(report):
    reset_scene()

    core_top = STAR_HEIGHT                      # 亮尖顶面 = 2.50
    tip_bottom = core_top - 0.34                # 亮尖段
    body_top = tip_bottom

    parts = []
    # 基座：不加噪声，底面精确落在 Z=0（左右两件都不得靠位移贴地，
    # 否则 ±1 m 偏移会被烘进顶点，几何相同的性质就没了）
    base = cylinder("base", 0.50, 0.14, (0.0, 0.0, 0.07), verts=10)
    flat(base)
    assign(base, "M_OBS_Marble")
    parts.append(base)

    # 主晶体：下段粗台 + 上段收口（整体精确到 2.16，亮尖再补到 2.50）
    lower_h = 0.95
    lower = cone("main_lower", 0.42, 0.34, lower_h, (0.0, 0.0, 0.14 + lower_h / 2), verts=12)
    flat(lower)
    assign(lower, "M_OBS_Aqua")
    parts.append(lower)

    upper_h = body_top - (0.14 + lower_h)
    upper = cone("main_upper", 0.34, 0.13, upper_h, (0.0, 0.0, 0.14 + lower_h + upper_h / 2), verts=12)
    flat(upper)
    assign(upper, "M_OBS_Aqua")
    parts.append(upper)

    # 发光亮尖
    tip = cone("main_tip", 0.13, 0.0, 0.34, (0.0, 0.0, body_top + 0.17), verts=12)
    flat(tip)
    assign(tip, "M_OBS_StarWhite")
    parts.append(tip)

    # 3 个细节小晶体：横向距离必须小于该高度处主晶体的半径，否则会脱在半空
    # （主晶体在 Z=0.5~0.8 处半径约 0.36~0.39）
    for i, (dx, dy, dz, r, h, tilt_x, tilt_y, mat) in enumerate([
        (0.30, -0.20, 0.30, 0.13, 0.62, 12.0, -18.0, "M_OBS_Aqua"),
        (-0.26, 0.22, 0.20, 0.10, 0.48, -15.0, 20.0, "M_OBS_Aqua"),
        (0.05, 0.30, 0.50, 0.075, 0.36, 22.0, 8.0, "M_OBS_StarWhite"),
    ]):
        c = cone(f"detail_{i}", r, 0.0, h,
                 (dx, dy, 0.14 + dz + h / 2),
                 verts=6,
                 rot=(math.radians(tilt_x), math.radians(tilt_y), 0.0))
        flat(c)
        assign(c, mat)
        parts.append(c)

    # 2 颗暖金星火（设计文档：冷环境里要有暖色焦点）
    for i, (dx, dy, dz) in enumerate([(0.46, 0.10, 1.55), (-0.40, -0.30, 1.95)]):
        s = ico(f"spark_{i}", 0.055, (dx, dy, dz), subdiv=1)
        smooth(s)
        assign(s, "M_OBS_StarWhite")
        parts.append(s)

    merged = join(parts, "OBS_StarFragment")

    # 复制成左右两件：只改 location.y，几何数据共享后再各自独立
    right = merged.copy()
    right.data = merged.data.copy()
    bpy.context.scene.collection.objects.link(right)
    merged.name = "OBS_StarFragment_Left"
    merged.data.name = "OBS_StarFragment_Left"
    right.name = "OBS_StarFragment_Right"
    right.data.name = "OBS_StarFragment_Right"

    merged.location.y = LEFT_Y_OFFSET
    right.location.y = RIGHT_Y_OFFSET

    # ---- 自检 ----
    h_left = vertex_hash(merged)
    h_right = vertex_hash(right)
    if h_left != h_right:
        fail(f"左右几何不一致: {h_left} vs {h_right}")
    dy = abs(merged.location.y - right.location.y)
    if abs(dy - 2.0) > 1e-6:
        fail(f"左右 Y 偏移 {dy} != 2.0")

    b = bounds([merged, right])
    tris = tri_count([merged, right])
    height = b["size"][2]
    if abs(height - STAR_HEIGHT) > 0.03:
        fail(f"星之碎片高度 {height} != {STAR_HEIGHT}")
    if abs(b["z"][0]) > 0.01:
        fail(f"星之碎片未落地，min_z={b['z'][0]}")
    if tris > STAR_MAX_TRIS:
        fail(f"星之碎片面数 {tris} > {STAR_MAX_TRIS}")

    report["OBS_StarFragment_Left"] = dict(
        size=b["size"], tris=tris, vhash=h_left, y_center=round(merged.location.y, 3))
    report["OBS_StarFragment_Right"] = dict(
        size=b["size"], tris=tris, vhash=h_right, y_center=round(right.location.y, 3))
    report["star_fragment_pair"] = dict(
        geometry_identical=(h_left == h_right), delta_y=round(dy, 6))

    export([merged], "OBS_StarFragment_Left")
    export([right], "OBS_StarFragment_Right")
    preview("OBS_StarFragment_Left", [merged], "OBS_StarFragment_Left")


# --------------------------------------------------------------------------
# 资产 3：云层缺口（两块 3×8×1，沿 X 留 1 m）
# --------------------------------------------------------------------------

def build_cloud_gap(report):
    reset_scene()
    blocks = []
    inner = GAP_WIDTH / 2.0

    def clamp_inner(obj, sgn):
        """把内壁顶点钉在 |x| = inner。

        云噪声会把内壁往里推，实测吃掉 0.063 m（1.0 → 0.937）。缺口是玩法尺寸，
        不能被噪声改；所以噪声只允许影响外轮廓，内壁一律钉死。
        """
        for v in obj.data.vertices:
            if sgn < 0.0 and v.co.x > -inner:
                v.co.x = -inner
            elif sgn > 0.0 and v.co.x < inner:
                v.co.x = inner

    for tag, sgn in (("A", -1.0), ("B", 1.0)):
        cx = sgn * (inner + GAP_BLOCK_X / 2.0)
        blk = cube(f"gap_{tag}", GAP_BLOCK_X, GAP_BLOCK_Y, GAP_BLOCK_Z,
                   loc=(cx, 0.0, GAP_BLOCK_Z / 2.0))
        activate(blk)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        subdivide(blk, 3)
        cloud_noise(blk, strength=0.025)
        clamp_inner(blk, sgn)
        smooth(blk)
        assign(blk, "M_OBS_Marble")
        blocks.append(blk)

    # 缺口两侧内壁的受光面：贴在块的内壁上，不侵入缺口
    for tag, sgn in (("A", -1.0), ("B", 1.0)):
        cx = sgn * (inner - 0.025)
        lip = cube(f"lip_{tag}", 0.05, GAP_BLOCK_Y * 0.96, 0.42,
                   loc=(cx, 0.0, GAP_BLOCK_Z - 0.30))
        activate(lip)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        clamp_inner(lip, sgn)
        assign(lip, "M_OBS_Gold")
        blocks.append(lip)

    # 两朵浮在缺口上方的碎云（不封住缺口，仅作点缀）
    for i, (x, y, z, r) in enumerate([(-1.9, 3.2, 1.25, 0.26), (2.1, -3.0, 1.32, 0.22)]):
        w = ico(f"wisp_{i}", r, (x, y, z), subdiv=2)
        cloud_noise(w, strength=0.06, scale=0.4)
        smooth(w)
        assign(w, "M_OBS_CloudSea")
        blocks.append(w)

    gap = join(blocks, "OBS_CloudGap")

    # ---- 自检 ----
    b = drop_to_ground([gap])
    # 缺口宽度：只看中央走廊（|Y|<2、Z<0.8）内，左右块之间的空档
    xs = sorted((gap.matrix_world @ v.co) for v in gap.data.vertices)
    cor = [p for p in xs if abs(p.y) < 2.0 and p.z < 0.8]
    left_max = max((p.x for p in cor if p.x < 0.0), default=None)
    right_min = min((p.x for p in cor if p.x > 0.0), default=None)
    if left_max is None or right_min is None:
        fail("找不到缺口两侧的几何")
    measured_gap = round(right_min - left_max, 3)

    tris = tri_count([gap])
    if abs(measured_gap - GAP_WIDTH) > 0.06:
        fail(f"缺口宽 {measured_gap} != {GAP_WIDTH}")
    if abs(b["z"][0]) > 0.01:
        fail(f"云层缺口未落地，min_z={b['z'][0]}")
    if tris > GAP_MAX_TRIS:
        fail(f"云层缺口面数 {tris} > {GAP_MAX_TRIS}")

    report["OBS_CloudGap"] = dict(
        size=b["size"], tris=tris, gap=measured_gap,
        nominal_footprint=(GAP_BLOCK_X * 2 + GAP_WIDTH, GAP_BLOCK_Y))

    export([gap], "OBS_CloudGap")
    preview("OBS_CloudGap", [gap], "OBS_CloudGap")


# --------------------------------------------------------------------------

def main():
    report = {}
    build_cloud_arch(report)
    build_star_fragment(report)
    build_cloud_gap(report)
    reset_scene()

    print()
    print("OBSTACLE_REPORT " + json.dumps(report, ensure_ascii=False))
    log("四件资产全部通过自检")


if __name__ == "__main__":
    main()

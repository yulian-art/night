"""Build StarJourney_Assets_Preview.blend - all generated FBX assets laid out for inspection.

Run:  blender --background --python build_asset_preview.py
"""
import bpy, math
from pathlib import Path
from mathutils import Vector

MODELS = Path("D:/UE/Projects/StarJourney/Content/StarJourney/Models")
OUT = Path("D:/UE/Projects/StarJourney/BlenderScripts")
RENDERS = OUT / "Preview"
BLEND = OUT / "StarJourney_Assets_Preview.blend"
for d in (OUT, RENDERS):
    d.mkdir(parents=True, exist_ok=True)

RES_X, RES_Y = 1500, 900
ASPECT = RES_X / RES_Y
ELEV, AZI = math.radians(50.0), math.radians(-80.0)
LABEL_RATIO = 0.042

bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene

def upd():
    bpy.context.view_layer.update()

def bbox(objs):
    upd()
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == 'MESH' for c in o.bound_box]
    if not pts:
        return None
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))

def fit_ortho(cam, points, margin=1.08):
    """Ortho scale that frames exactly these world points for the current camera."""
    upd()
    inv = cam.matrix_world.inverted()
    xs, ys = [], []
    for p in points:
        v = inv @ p
        xs.append(abs(v.x)); ys.append(abs(v.y))
    return max(2.0 * max(max(xs), max(ys) * ASPECT) * margin, 1e-3)

# ---------------- import every asset ----------------
cats = []
for group in ["WindPost", "CloudWhale"]:
    for cat in ["ENV", "OBS", "DEC"]:
        src = MODELS / group / cat
        items = []
        if src.is_dir():
            for f in sorted(src.glob("*.fbx")):
                before = set(bpy.data.objects)
                bpy.ops.import_scene.fbx(filepath=str(f))
                roots = [o for o in bpy.data.objects if o not in before and o.parent is None]
                for o in roots:
                    o.name = f.stem
                items.append({"name": f.stem, "roots": roots})
        if items:
            coll = bpy.data.collections.new(f"{group}_{cat}")
            scn.collection.children.link(coll)
            cats.append({"label": f"{group}_{cat}", "coll": coll, "items": items})

# ---------------- rows: one per category, big assets split from small ones ----------------
rows = []
for cat in cats:
    for it in cat["items"]:
        b = bbox(it["roots"])
        it["size"] = max(b[1].x - b[0].x, b[1].y - b[0].y, b[1].z - b[0].z) if b else 1.0
    for it in sorted(cat["items"], key=lambda i: -i["size"]):
        if rows and rows[-1]["cat"] is cat and it["size"] * 4.0 >= rows[-1]["ref"]:
            rows[-1]["items"].append(it)
        else:
            rows.append({"cat": cat, "items": [it], "ref": it["size"]})
for n, r in enumerate(rows):
    full = len(r["items"]) == len(r["cat"]["items"])
    r["label"] = r["cat"]["label"] if full else f"{r['cat']['label']} ({r['items'][0]['size']:.0f}u)"

# ---------------- material for the self-lit labels ----------------
label_mat = bpy.data.materials.new("LabelInk")
label_mat.use_nodes = True
lb = label_mat.node_tree.nodes["Principled BSDF"]
lb.inputs["Base Color"].default_value = (0.96, 0.97, 1.0, 1.0)
lb.inputs["Emission Color"].default_value = (0.90, 0.93, 1.0, 1.0)
lb.inputs["Emission Strength"].default_value = 2.0

# ---------------- lay out: ground each asset at z=0, flat label in front ----------------
y = 0.0
for r in rows:
    boxes = [bbox(i["roots"]) for i in r["items"]]
    w = max(b[1].x - b[0].x for b in boxes)
    d = max(b[1].y - b[0].y for b in boxes)
    cell = w + max(w * 0.35, 2.0)
    x0 = -cell * len(r["items"]) / 2.0 + cell / 2.0
    label_y = y - d - max(d * 0.22, 1.2)

    for i, it in enumerate(r["items"]):
        upd()
        b = bbox(it["roots"])
        dx = (x0 + i * cell) - (b[0].x + b[1].x) / 2.0
        dy = (y - d / 2.0) - (b[0].y + b[1].y) / 2.0
        for o in it["roots"]:
            o.location.x += dx
            o.location.y += dy
            o.location.z += -b[0].z
            for c in list(o.users_collection):
                c.objects.unlink(o)
            r["cat"]["coll"].objects.link(o)

        # flat on the ground, +Y away from camera -> readable from the preview view
        txt = bpy.data.curves.new(f"lbl_{it['name']}", type='FONT')
        txt.body = it["name"]
        txt.align_x = 'CENTER'
        txt.align_y = 'TOP'
        txt.size = max(w * LABEL_RATIO, 0.22)
        tob = bpy.data.objects.new(f"LABEL_{it['name']}", txt)
        tob.data.materials.append(label_mat)
        r["cat"]["coll"].objects.link(tob)
        tob.location = Vector((x0 + i * cell, label_y, 0.05))

    r["cy"] = y - d / 2.0
    r["h"] = max(b[1].z - b[0].z for b in boxes)
    print(f"row {r['label']:26s} n={len(r['items']):2d} w={w:7.1f} d={d:7.1f} h={r['h']:6.1f}")
    y -= (d + max(d, 8.0) + abs(label_y - (y - d)))

upd()
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
all_pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
print("TOTAL ASSETS:", sum(len(r['items']) for r in rows), "| meshes:", len(meshes))

# ---------------- world, ground, lights ----------------
world = bpy.data.worlds.new("World"); scn.world = world; world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.035, 0.05, 0.09, 1.0)
bg.inputs[1].default_value = 1.0

gmat = bpy.data.materials.new("GroundMat"); gmat.use_nodes = True
gbsdf = gmat.node_tree.nodes["Principled BSDF"]
gbsdf.inputs["Base Color"].default_value = (0.05, 0.062, 0.085, 1.0)
gbsdf.inputs["Roughness"].default_value = 0.92

mn = Vector((min(p.x for p in all_pts), min(p.y for p in all_pts), min(p.z for p in all_pts)))
mx = Vector((max(p.x for p in all_pts), max(p.y for p in all_pts), max(p.z for p in all_pts)))
half = max(mx.x - mn.x, mx.y - mn.y) * 3.0 + 500.0
gmesh = bpy.data.meshes.new("PreviewGround")
gmesh.from_pydata([(-half, -half, 0), (half, -half, 0), (half, half, 0), (-half, half, 0)], [], [(0, 1, 2, 3)])
gmesh.update()
ground = bpy.data.objects.new("PreviewGround", gmesh)
ground.data.materials.append(gmat)
scn.collection.objects.link(ground)

for name, energy, rot in [("KeySun", 5.0, (0.80, 0.0, 0.85)), ("FillSun", 2.0, (1.15, 0.0, 3.9))]:
    ld = bpy.data.lights.new(name, type='SUN'); ld.energy = energy; ld.angle = 0.35
    ob = bpy.data.objects.new(name, ld); scn.collection.objects.link(ob)
    ob.rotation_euler = rot

try:
    scn.render.engine = 'BLENDER_EEVEE_NEXT'
except TypeError:
    scn.render.engine = 'BLENDER_EEVEE'
scn.render.resolution_x, scn.render.resolution_y = RES_X, RES_Y
scn.render.image_settings.file_format = 'PNG'

cd = bpy.data.cameras.new("PreviewCam"); cd.type = 'ORTHO'; cd.clip_start = 1.0
cam = bpy.data.objects.new("PreviewCam", cd); scn.collection.objects.link(cam)
scn.camera = cam

def aim(target, radius):
    direction = Vector((math.cos(ELEV) * math.cos(AZI), math.cos(ELEV) * math.sin(AZI), math.sin(ELEV)))
    dist = radius * 2.5 + 500.0
    cam.location = target + direction * dist
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.clip_end = dist * 4.0

for o in bpy.data.objects:
    o.select_set(False)

# ---------------- one true-scale render per row (rows are size-coherent) ----------------
def visible_only(keys):
    """Show only these mesh/font objects; hide every other mesh/font."""
    for o in bpy.data.objects:
        if o.type in {'MESH', 'FONT'} and o.name != 'PreviewGround':
            o.hide_render = o.name not in keys
    upd()

for n, r in enumerate(rows):
    keys = {o.name for it in r["items"] for o in it["roots"]}
    keys |= {f"LABEL_{it['name']}" for it in r["items"]}
    visible_only(keys)
    pts = [o.matrix_world @ Vector(c) for o in bpy.data.objects
           if o.name in keys and o.type in {'MESH', 'FONT'} for c in o.bound_box]
    bmn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    bmx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    aim((bmn + bmx) / 2.0, max(bmx.x - bmn.x, bmx.y - bmn.y, bmx.z - bmn.z) / 2.0)
    cam.data.ortho_scale = fit_ortho(cam, pts)
    scn.render.filepath = str(RENDERS / f"{n:02d}_{r['label']}.png")
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED {r['label']}  n={len(r['items'])} ortho={cam.data.ortho_scale:.2f}")

# ---------------- contact sheet: every asset normalised to the same size ----------------
SHEET = RENDERS / "CONTACT_SHEET.png"
SHEET_COLS = 7
SHEET_CELLS = [it for r in rows for it in r["items"]]
visible_only({o.name for it in SHEET_CELLS for o in it["roots"]})

# remember each asset's true transform, then normalise for the sheet
saved = {}
for it in SHEET_CELLS:
    saved[it["name"]] = [(o, o.location.copy(), o.scale.copy()) for o in it["roots"]]

cell_x, cell_y = 3.1, 3.5
sheet_h = math.ceil(len(SHEET_CELLS) / SHEET_COLS)
for idx, it in enumerate(SHEET_CELLS):
    upd()
    b = bbox(it["roots"])
    span = max(b[1].x - b[0].x, b[1].y - b[0].y, b[1].z - b[0].z)
    s = 1.6 / span if span > 1e-6 else 1.0
    cx = (idx % SHEET_COLS - (SHEET_COLS - 1) / 2.0) * cell_x
    cy = (sheet_h // 2 - idx // SHEET_COLS) * cell_y
    for o, loc0, scale0 in saved[it["name"]]:
        o.location = loc0 * s
        o.scale = scale0 * s
    upd()
    b = bbox(it["roots"])
    dx = cx - (b[0].x + b[1].x) / 2.0
    dy = cy - (b[0].y + b[1].y) / 2.0
    dz = -b[0].z
    for o, loc0, scale0 in saved[it["name"]]:
        o.location.x += dx; o.location.y += dy; o.location.z += dz

# place the labels in a fixed row under the grid, all the same size
sheet_font = 0.17
for idx, it in enumerate(SHEET_CELLS):
    tob = bpy.data.objects.get(f"LABEL_{it['name']}")
    if tob is None:
        continue
    tob.hide_render = False
    tob.data.size = sheet_font
    tob.location = Vector(((idx % SHEET_COLS - (SHEET_COLS - 1) / 2.0) * cell_x,
                           (sheet_h // 2 - idx // SHEET_COLS) * cell_y - 1.15,
                           0.05))
    tob.rotation_euler = (0, 0, 0)

upd()
sheet_pts = [o.matrix_world @ Vector(c) for o in bpy.data.objects
             if o.type in {'MESH', 'FONT'} and o.name != 'PreviewGround'
             and o.hide_render is False for c in o.bound_box]
sc = Vector((sum(p.x for p in sheet_pts) / len(sheet_pts), 0.0, 0.0))
bmn = Vector((min(p.x for p in sheet_pts), min(p.y for p in sheet_pts), min(p.z for p in sheet_pts)))
bmx = Vector((max(p.x for p in sheet_pts), max(p.y for p in sheet_pts), max(p.z for p in sheet_pts)))
aim((bmn + bmx) / 2.0, max(bmx.x - bmn.x, bmx.y - bmn.y, bmx.z - bmn.z) / 2.0)
cam.data.ortho_scale = fit_ortho(cam, sheet_pts, margin=1.03)
scn.render.filepath = str(SHEET)
bpy.ops.render.render(write_still=True)
print(f"RENDERED CONTACT_SHEET  ortho={cam.data.ortho_scale:.2f}")

# ---------------- restore true scale and save the .blend in its browsable state ----------------
for it in SHEET_CELLS:
    for o, loc0, scale0 in saved[it["name"]]:
        o.location = loc0
        o.scale = scale0
for o in bpy.data.objects:
    o.hide_render = o.name.startswith("LABEL_") or o.name == "PreviewGround"
    if o.type == 'FONT':
        o.hide_render = False
    o.hide_set(False)
    o.select_set(False)

bmn_all = Vector((min(p.x for p in all_pts), min(p.y for p in all_pts), min(p.z for p in all_pts)))
bmx_all = Vector((max(p.x for p in all_pts), max(p.y for p in all_pts), max(p.z for p in all_pts)))
aim((bmn_all + bmx_all) / 2.0, max(bmx_all.x - bmn_all.x, bmx_all.y - bmn_all.y) / 2.0)
cam.data.ortho_scale = fit_ortho(cam, all_pts)
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
print("SAVED BLEND:", BLEND)
print(f"ASSET COUNT: {len(SHEET_CELLS)}")
print("DONE")
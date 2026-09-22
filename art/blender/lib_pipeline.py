"""Shared Blender-side pipeline for normalizing the CC0 character assets.

Used only by normalize_hero.py / normalize_fox.py, always headless:

    blender --background --python art/blender/normalize_hero.py

Nothing here imports bpy at module level in a way that would let the file be
imported outside Blender by accident -- the scripts are Blender entry points.

Why this file exists rather than two copies: the two characters differ only in
their spec (target height, bone count, which bones reveal facing), so the
fragile parts -- measuring the bind pose, deriving facing from bones, applying
transforms, asserting the result -- live in exactly one place.
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

# ---------------------------------------------------------------------------
# Tuning
# ---------------------------------------------------------------------------

# A forward axis must be close to horizontal: characters stand upright, so a
# head/hips vector (|z| ~ 1.0) can never be a facing indicator. Candidates that
# fail this filter are still printed as evidence, just never selected.
HORIZONTAL_MAX = 0.35

# Two passing candidates must agree to this cosine before we trust them.
AGREEMENT_MIN = 0.5

# Feet slab: the ground contact is the lowest 5% of the height. The centroid of
# that slab is the "feet landing point" the origin is moved to.
FEET_SLAB_FRACTION = 0.05

# Tolerance on the normalized height, in metres (doc: 180/55 cm +/- 1 cm).
HEIGHT_TOLERANCE_M = 0.01

# Tolerance on the final ground contact and facing.
GROUND_TOLERANCE_M = 1e-3
FACING_TOLERANCE_COS = 0.999  # ~2.5 degrees


class Spec:
    """Everything that differs between the two characters."""

    def __init__(self, key, glb, fbx_name, target_height_m, expected_bones,
                 armature_hint, sk_name, skel_name, expected_meshes,
                 forward_candidates, notes=""):
        self.key = key
        self.glb = glb
        self.fbx_name = fbx_name
        self.target_height_m = target_height_m
        self.expected_bones = expected_bones
        self.armature_hint = armature_hint
        self.sk_name = sk_name          # mesh object name, e.g. SK_Hero
        self.skel_name = skel_name      # armature object name, e.g. SKEL_Hero
        self.expected_meshes = expected_meshes
        # Each candidate is ("bone_tail", bone) for a bone whose tail continues
        # the facing direction (a foot bone points ankle -> toe), or
        # ("bone_bone", a, b) for head(a) -> head(b).
        self.forward_candidates = forward_candidates
        self.notes = notes


def repo_root():
    """Repository root, derived from this file's location (art/blender/...)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def log(message):
    print("[normalize] %s" % message, flush=True)


# ---------------------------------------------------------------------------
# Scene setup and import
# ---------------------------------------------------------------------------

def reset_scene():
    """Empty factory scene: deterministic regardless of the user's startup file."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    log("scene reset (empty factory settings)")


def import_glb(path):
    if not os.path.isfile(path):
        raise AssertionError("source GLB not found: %s" % path)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    imported = [o for o in bpy.data.objects if o not in before]
    if not imported:
        raise AssertionError("glTF import produced no objects: %s" % path)

    # Keep every imported action alive across the rest-pose clear below and the
    # export, so the clip list survives.
    for action in bpy.data.actions:
        action.use_fake_user = True

    log("imported %d objects from %s" % (len(imported), os.path.basename(path)))
    return imported


def drop_icosphere():
    """Remove the invisible helper sphere if the file carries one.

    Defensive on purpose: neither GLB in art/thirdparty/cc0 actually contains an
    Icosphere (verified by parsing the glTF JSON and grepping the binaries), but
    the brief and the design doc both call for excluding it, and a stray
    untextured sphere would silently inflate the bounding box. Harmless when
    absent.
    """
    removed = []
    for obj in list(bpy.data.objects):
        if obj.name.lower().startswith("icosphere"):
            removed.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)
    if removed:
        log("removed helper object(s): %s" % ", ".join(removed))
    else:
        log("no Icosphere present (expected for these files)")
    return removed


def find_armature(imported, hint):
    """Pick the armature that carries the character.

    The glTF importer can produce more than one armature when the file holds
    several skins, so prefer the one that actually parents a mesh, then the
    largest by bone count. The count is asserted separately.
    """
    armatures = [o for o in imported if o.type == "ARMATURE" and o.name in bpy.data.objects]
    if not armatures:
        raise AssertionError("no armature was imported")

    def parents_a_mesh(arm):
        return any(m.parent is arm for m in bpy.data.objects if m.type == "MESH")

    armatures.sort(key=lambda a: (parents_a_mesh(a), len(a.data.bones)), reverse=True)
    chosen = armatures[0]
    log("armature objects found: %s" % ", ".join("%s(%d bones)" % (a.name, len(a.data.bones))
                                                for a in armatures))
    if hint and chosen.name != hint:
        log("note: expected armature name %r, using %r" % (hint, chosen.name))
    return chosen, armatures


def mesh_objects(imported):
    meshes = [o for o in imported if o.type == "MESH" and o.name in bpy.data.objects]
    if not meshes:
        raise AssertionError("no mesh objects were imported")
    return meshes


def assert_bone_count(armatures, expected):
    """Assert the skeleton size, counting unique bone names across armatures.

    A glTF file may declare one skin per mesh, all sharing one joint set; if the
    importer materialises that as several armature objects, each still holds the
    same 62 bones. Counting unique names states the requirement ("62 bones")
    without depending on how many objects the importer chose to make.
    """
    per_object = {a.name: len(a.data.bones) for a in armatures}
    unique = set()
    for a in armatures:
        unique.update(b.name for b in a.data.bones)

    log("bone counts per armature: %s; unique bone names: %d" %
        (per_object, len(unique)))
    if len(unique) != expected:
        raise AssertionError(
            "skeleton mismatch: expected %d unique bones, found %d (%s). "
            "Names: %s" % (expected, len(unique), per_object,
                           sorted(unique)[:80]))
    if len(armatures) > 1:
        log("warning: importer produced %d armature objects sharing %d bones"
            % (len(armatures), len(unique)))


def clear_pose(armature):
    """Force the rest pose so measurements describe the bind pose.

    The importer may leave an action assigned, which would make the bounding box
    depend on animation frame 0 instead of the rig's rest pose.
    """
    if armature.animation_data:
        armature.animation_data.action = None
    for pb in armature.pose.bones:
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

def _evaluated(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    return obj.evaluated_get(depsgraph)


def world_bounds(meshes):
    """World-space AABB of the evaluated meshes (skinning applied).

    Evaluated rather than raw data: these meshes are skinned, and the modifier
    result is what will actually be exported.
    """
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    for obj in meshes:
        ev = _evaluated(obj)
        matrix = ev.matrix_world
        for corner in ev.bound_box:
            p = matrix @ Vector(corner)
            for k in range(3):
                lo[k] = min(lo[k], p[k])
                hi[k] = max(hi[k], p[k])
    if lo[0] == float("inf"):
        raise AssertionError("could not measure any mesh")
    return Vector(lo), Vector(hi)


def feet_centroid(meshes, min_z, height):
    """XY centre of the lowest slab: where the character touches the ground.

    Using the ground-contact geometry rather than the whole bounding box keeps
    the origin under the feet even when a tail or an outstretched arm would drag
    the box centre away from the stance.
    """
    cut = min_z + FEET_SLAB_FRACTION * height
    sx = sy = 0.0
    n = 0
    for obj in meshes:
        ev = _evaluated(obj)
        matrix = ev.matrix_world
        mesh = ev.to_mesh()
        try:
            for v in mesh.vertices:
                p = matrix @ v.co
                if p.z <= cut:
                    sx += p.x
                    sy += p.y
                    n += 1
        finally:
            ev.to_mesh_clear()
    if n == 0:
        log("warning: no vertices in the feet slab; using the bounding box centre")
        return None, 0
    return Vector((sx / n, sy / n)), n


def bone_point(armature, name, which):
    """World position of a bone's head or tail in the rest pose.

    Rest-pose (head_local/tail_local) rather than pose space, so the facing
    derivation cannot be perturbed by whatever pose the importer left behind.
    """
    bone = armature.data.bones.get(name)
    if bone is None:
        return None
    local = bone.head_local if which == "head" else bone.tail_local
    return armature.matrix_world @ Vector(local)


def evaluate_candidates(armature, candidates):
    """Return (label, direction, horizontal_ratio, raw_vector) per candidate."""
    out = []
    for kind, *args in candidates:
        if kind == "bone_tail":
            (bone_name,) = args
            a = bone_point(armature, bone_name, "head")
            b = bone_point(armature, bone_name, "tail")
            label = "%s head->tail" % bone_name
        elif kind == "bone_bone":
            first, second = args
            a = bone_point(armature, first, "head")
            b = bone_point(armature, second, "head")
            label = "%s -> %s" % (first, second)
        else:
            raise AssertionError("unknown candidate kind: %r" % (kind,))

        if a is None or b is None:
            log("   skip %-26s (bone missing)" % label)
            continue
        v = b - a
        length = v.length
        if length < 1e-6:
            log("   skip %-26s (zero length)" % label)
            continue
        out.append((label, v / length, abs(v.normalized().z), v))
    return out


def derive_facing(armature, candidates):
    """Derive the current facing from bones, with printed evidence.

    Never guesses: if no candidate is horizontal enough, or if the horizontal
    candidates disagree with each other, this raises and the operator decides.
    """
    evaluated = evaluate_candidates(armature, candidates)
    log("facing candidates (Blender space, +Y is backwards when facing -Y):")
    for label, unit, zr, _raw in evaluated:
        mark = "OK " if zr <= HORIZONTAL_MAX else "   "
        yaw = math.degrees(math.atan2(unit.y, unit.x))
        log("   %s%-26s dir=(%7.4f,%7.4f,%7.4f) |z|=%.3f yaw=%8.2f"
            % (mark, label, unit.x, unit.y, unit.z, zr, yaw))

    passing = [(l, u) for (l, u, zr, _r) in evaluated if zr <= HORIZONTAL_MAX]
    if not passing:
        raise AssertionError(
            "no horizontal bone candidate for facing; refusing to guess. "
            "Candidates were: %s" % [l for l, _u, _z, _r in evaluated])

    primary_label, primary = passing[0]
    agreeing = []
    for label, unit in passing[1:]:
        dot = primary.dot(unit)
        if dot <= -AGREEMENT_MIN:
            raise AssertionError(
                "ambiguous facing: %r (%s) and %r (%s) point opposite ways"
                % (primary_label, tuple(round(c, 3) for c in primary),
                   label, tuple(round(c, 3) for c in unit)))
        if dot >= AGREEMENT_MIN:
            agreeing.append((label, dot))

    if not agreeing:
        raise AssertionError(
            "only one horizontal candidate (%r); no corroboration, refusing to guess"
            % primary_label)

    log("facing evidence: primary=%r; corroborated by %s"
        % (primary_label, ", ".join("%s(dot=%.3f)" % (l, d) for l, d in agreeing)))
    return primary, primary_label


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def _select_only(objects, active):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active


def make_single_user(objects):
    """transform_apply refuses multi-user data; give each object its own copy."""
    for obj in objects:
        if obj.data is not None and obj.data.users > 1:
            obj.data = obj.data.copy()
            log("made single-user data for %s" % obj.name)


def apply_transforms(objects, active):
    make_single_user(objects)
    _select_only(objects, active)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.context.view_layer.update()


def angle_to_minus_y(forward):
    """Yaw (radians) that rotates `forward` onto -Y."""
    current = math.atan2(forward.y, forward.x)
    target = math.atan2(-1.0, 0.0)
    delta = target - current
    while delta > math.pi:
        delta -= 2.0 * math.pi
    while delta < -math.pi:
        delta += 2.0 * math.pi
    return delta


def normalize(spec, armature, meshes, imported):
    """Scale to the target height, put the feet at the origin, face -Y."""
    lo, hi = world_bounds(meshes)
    height = hi.z - lo.z
    log("bind-pose bounds before: min=(%.4f,%.4f,%.4f) max=(%.4f,%.4f,%.4f) height=%.4f m"
        % (lo.x, lo.y, lo.z, hi.x, hi.y, hi.z, height))
    if height <= 1e-6:
        raise AssertionError("degenerate bounds before normalization (height=%.6f)" % height)
    scale = spec.target_height_m / height
    log("scale factor = %.6f (target %.3f m)" % (scale, spec.target_height_m))

    forward, forward_label = derive_facing(armature, spec.forward_candidates)
    yaw = angle_to_minus_y(forward)
    log("facing: using %r; rotating Z by %.2f degrees to face -Y"
        % (forward_label, math.degrees(yaw)))

    # Scale about the world origin, then measure the scaled numbers directly
    # rather than scaling the old ones: the feet slab has to be located in the
    # geometry that actually exists after scaling.
    roots = [o for o in imported if o.parent is None and o.name in bpy.data.objects]
    if not roots:
        raise AssertionError("no root object found to transform")
    S = Matrix.Diagonal(Vector((scale, scale, scale, 1.0)))
    for root in roots:
        root.matrix_world = S @ root.matrix_world
    bpy.context.view_layer.update()

    lo, hi = world_bounds(meshes)
    height = hi.z - lo.z
    centroid, samples = feet_centroid(meshes, lo.z, height)
    if centroid is None:
        centroid = Vector(((lo.x + hi.x) * 0.5, (lo.y + hi.y) * 0.5))
    log("after scale: height=%.4f m  min_z=%.4f  feet centroid XY=(%.4f, %.4f) from %d verts"
        % (height, lo.z, centroid.x, centroid.y, samples))

    T = Matrix.Translation(Vector((-centroid.x, -centroid.y, -lo.z)))
    R = Matrix.Rotation(yaw, 4, "Z")
    M = R @ T
    for root in roots:
        root.matrix_world = M @ root.matrix_world
    bpy.context.view_layer.update()

    apply_transforms(roots + meshes, roots[0])
    log("transforms applied on %d objects" % (len(roots) + len(meshes)))


def rename_assets(spec, armature, meshes):
    """Name the assets and their data blocks for the UE import step."""
    armature.name = spec.skel_name
    armature.data.name = spec.skel_name
    for index, obj in enumerate(sorted(meshes, key=lambda o: o.name)):
        # One skeletal mesh per character; extra material-split parts keep a
        # suffix so nothing collides.
        name = spec.sk_name if index == 0 else "%s_%02d" % (spec.sk_name, index)
        obj.name = name
        if obj.data is not None:
            obj.data.name = name
    log("renamed: armature=%s meshes=%s" % (spec.skel_name, [o.name for o in meshes]))


# ---------------------------------------------------------------------------
# Assertions and export
# ---------------------------------------------------------------------------

def verify(spec, armature, meshes):
    """Post-conditions. Any failure raises, so no FBX is produced."""
    lo, hi = world_bounds(meshes)
    height = hi.z - lo.z
    forward, label = derive_facing(armature, spec.forward_candidates)

    checks = []
    ok_ground = abs(lo.z) < GROUND_TOLERANCE_M
    checks.append(("min_z ~ 0", ok_ground, "min_z=%.6f" % lo.z))

    ok_height = abs(height - spec.target_height_m) <= HEIGHT_TOLERANCE_M
    checks.append(("height == %.2f m +/- %.0f cm" % (spec.target_height_m, HEIGHT_TOLERANCE_M * 100),
                   ok_height, "height=%.4f m" % height))

    facing_dot = forward.dot(Vector((0.0, -1.0, 0.0)))
    ok_facing = facing_dot >= FACING_TOLERANCE_COS
    checks.append(("facing ~= -Y", ok_facing,
                   "%s -> (%0.4f, %0.4f, %0.4f) dot=%.6f"
                   % (label, forward.x, forward.y, forward.z, facing_dot)))

    # Facing must not have been achieved by tilting the character over: the
    # height axis stays vertical because we only ever rotate about Z, and this
    # catches a future edit that breaks that.
    ok_upright = abs(forward.z) <= HORIZONTAL_MAX
    checks.append(("facing axis still horizontal", ok_upright, "|z|=%.4f" % abs(forward.z)))

    log("assertions:")
    for name, ok, detail in checks:
        log("   [%s] %-34s %s" % ("PASS" if ok else "FAIL", name, detail))
    failed = [name for name, ok, _ in checks if not ok]
    if failed:
        raise AssertionError("normalization assertions failed: %s" % ", ".join(failed))

    log("final bounds: min=(%.4f,%.4f,%.4f) max=(%.4f,%.4f,%.4f) height=%.4f m"
        % (lo.x, lo.y, lo.z, hi.x, hi.y, hi.z, height))
    return height


def report_clips():
    """Print the clip names so the mapping table can be checked by hand."""
    actions = sorted(a.name for a in bpy.data.actions)
    log("clips in file: %d" % len(actions))
    for name in actions:
        log("   clip %s" % name)
    return actions


def export_fbx(spec, armature, meshes):
    out_dir = os.path.join(repo_root(), "art", "export")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, spec.fbx_name)

    _select_only(meshes + [armature], armature)
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        # Blender metres -> Unreal centimetres (doc section 3).
        global_scale=100.0,
        # Unreal wants Z forward / Y up at the FBX boundary.
        axis_forward="-Z",
        axis_up="Y",
        object_types={"ARMATURE", "MESH"},
        # Keep the skeleton exactly as authored: extra leaf bones would change
        # the exported bone count that the UE import step asserts.
        add_leaf_bones=False,
        use_armature_deform_only=False,
        # Every clip, baked, without key reduction.
        bake_anim=True,
        bake_anim_use_all_actions=True,
        bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True,
        bake_anim_simplify_factor=0.0,
        mesh_smooth_type="FACE",
        path_mode="AUTO",
    )
    if not os.path.isfile(path):
        raise AssertionError("FBX export reported success but no file exists: %s" % path)
    log("exported %s (%.1f KB)" % (path, os.path.getsize(path) / 1024.0))
    return path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(spec):
    log("=== %s ===" % spec.key)
    if spec.notes:
        log("note: %s" % spec.notes)

    reset_scene()
    imported = import_glb(os.path.join(repo_root(), spec.glb))
    drop_icosphere()

    armature, armatures = find_armature(imported, spec.armature_hint)
    assert_bone_count(armatures, spec.expected_bones)

    meshes = mesh_objects(imported)
    found = sorted(o.name for o in meshes)
    log("mesh objects: %s" % found)
    missing = [m for m in spec.expected_meshes if m not in found]
    if missing:
        # Reported, not fatal: which mesh carries which material is not part of
        # the normalization contract, but a missing expected part is worth
        # knowing before UE import.
        log("warning: expected mesh part(s) not present: %s" % missing)

    clear_pose(armature)
    clips = report_clips()
    normalize(spec, armature, meshes, imported)
    rename_assets(spec, armature, meshes)
    verify(spec, armature, meshes)
    path = export_fbx(spec, armature, meshes)

    log("=== %s done: bones=%d clips=%d fbx=%s ==="
        % (spec.key, len({b.name for a in armatures for b in a.data.bones}),
           len(clips), path))
    return path

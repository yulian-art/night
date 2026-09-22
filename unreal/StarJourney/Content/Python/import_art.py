"""Import the Blender-exported character FBX files as UE skeletal assets.

Run through Manage-StarJourney.ps1 -Action ImportArt (never by hand-dragging: a
manual import is not reproducible).

Why this script exists: the Blender export bakes a centimetre scale
(global_scale=100). Getting that wrong is the single most common art-pipeline
accident and it is silent - the character simply shows up 100x too big or too
small, and every later measurement inherits the error. So the import refuses to
report success unless the imported mesh measures the intended height.

Every engine API used here is wrapped defensively: the import and bounds
accessors have moved between UE versions, and a version mismatch must produce a
loud, specific failure rather than a silently empty asset.
"""
import json
import os
from pathlib import Path
import traceback
import unreal as u

ROOT = '/Game/StarJourney'
CHARACTERS = ROOT + '/Characters'

# Height tolerance in centimetres. Two centimetres is tight enough to catch a
# unit mistake of any magnitude (100x, 10x, 2.54x) while tolerating the small
# difference between the authored bounds and the imported ones.
TOLERANCE_CM = 2.0

TARGETS = (
    {
        'file': 'SK_Hero.fbx',
        'folder': CHARACTERS + '/Hero',
        'mesh': 'SK_Hero',
        'skeleton': 'SKEL_Hero',
        'anim_prefix': 'A_Hero_',
        'anim_blueprint': 'ABP_Hero',
        'height_cm': 180.0,
    },
    {
        'file': 'SK_Fox.fbx',
        'folder': CHARACTERS + '/Fox',
        'mesh': 'SK_Fox',
        'skeleton': 'SKEL_Fox',
        'anim_prefix': 'A_Fox_',
        'anim_blueprint': 'ABP_Fox',
        'height_cm': 55.0,
    },
)

# FBX import options. The key names are Interchange-era; older builds want
# "importAsSkeletal". A wrong key is not fatal here because the mesh is imported
# either way, and the bounds assertion below still catches a wrong result.
SKELETAL_OPTIONS = 'importAsSkeletal=true'


def project_dir():
    # project_dir() already returns an absolute path; converting it again would
    # add an API dependency for no benefit.
    return Path(u.Paths.project_dir())


def find_export_dir(warnings):
    """Locate the folder holding the Blender FBX export.

    The export lives outside the UE project in the source repository, so the
    caller may pass it explicitly with STAR_ART_EXPORT; otherwise the copies that
    Manage-StarJourney.ps1 places inside the project are used. Failing to find it
    is fatal: an empty import must never look like a successful one.
    """
    candidates = []
    override = os.environ.get('STAR_ART_EXPORT')
    if override:
        candidates.append(Path(override))
    candidates.append(project_dir() / 'art' / 'export')
    candidates.append(project_dir() / 'Saved' / 'ArtExport')
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise RuntimeError(
        'no art export directory found; looked in: '
        + '; '.join(str(c) for c in candidates)
        + '. Run the Blender export, or set STAR_ART_EXPORT.')


def ensure_folder(path, warnings):
    """Create a content folder, reporting a failure instead of raising.

    The import task creates missing folders itself on most builds; doing it here
    first means a permission problem is reported early and precisely.
    """
    if u.EditorAssetLibrary.does_directory_exist(path):
        return True
    created = u.EditorAssetLibrary.make_directory(path)
    if not created:
        warnings.append('could not create content folder: ' + path)
    return bool(created)


def import_mesh(target, export_root, warnings):
    """Import one FBX and return the resulting SkeletalMesh, or None."""
    source = export_root / target['file']
    if not source.is_file():
        raise RuntimeError('missing export: ' + str(source))

    ensure_folder(target['folder'], warnings)

    task = u.AssetImportTask()
    task.set_editor_property('filename', str(source))
    task.set_editor_property('destination_path', target['folder'])
    task.set_editor_property('destination_name', target['mesh'])
    task.set_editor_property('automated', True)
    task.set_editor_property('replace_existing', True)
    task.set_editor_property('save', True)
    try:
        task.set_editor_property('options', SKELETAL_OPTIONS)
    except Exception as exc:
        # An options string this build rejects must not abort the import.
        warnings.append('could not set import options on %s: %s' % (target['file'], exc))

    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    mesh_path = '%s/%s' % (target['folder'], target['mesh'])
    mesh = u.EditorAssetLibrary.load_asset(mesh_path)
    if mesh is None:
        # Report what did land, so the failure names the actual asset instead of
        # only the one that was expected.
        landed = u.EditorAssetLibrary.list_assets(target['folder'], recursive=False)
        raise RuntimeError(
            'import produced no asset at %s; the folder now holds: %s'
            % (mesh_path, ', '.join(landed) if landed else '(nothing)'))
    if not isinstance(mesh, u.SkeletalMesh):
        raise RuntimeError(
            '%s is a %s, not a SkeletalMesh; the FBX was imported as a static mesh'
            % (mesh_path, type(mesh).__name__))
    return mesh


def measure_height_cm(mesh, warnings):
    """Measure the mesh height in centimetres.

    Returns (height, accessor). UE units are centimetres, so the bounds extent is
    already the number to compare against. USkeletalMesh exposes imported bounds
    on most builds and plain bounds on others, and the Python binding returns
    either an FBoxSphereBounds or an (origin, extent) pair, so every combination
    is tried and the one that worked is recorded.
    """
    for accessor in ('get_imported_bounds', 'get_bounds'):
        method = getattr(mesh, accessor, None)
        if method is None:
            continue
        try:
            bounds = method()
        except Exception as exc:
            warnings.append('%s() failed on %s: %s' % (accessor, mesh.get_name(), exc))
            continue
        extent = getattr(bounds, 'box_extent', None)
        if extent is None and isinstance(bounds, (tuple, list)) and len(bounds) == 2:
            extent = bounds[1]
        z = getattr(extent, 'z', None)
        if z is None:
            warnings.append('%s() returned an unusable value on %s' % (accessor, mesh.get_name()))
            continue
        return float(z) * 2.0, accessor
    return None, 'no bounds accessor worked'


def rename_skeleton(mesh, target, warnings):
    """Give the auto-created Skeleton its canonical SKEL_ name."""
    try:
        skeleton = mesh.get_editor_property('skeleton')
    except Exception as exc:
        warnings.append('could not read the skeleton from %s: %s' % (target['mesh'], exc))
        skeleton = None
    if skeleton is None:
        warnings.append('no skeleton found on ' + target['mesh'])
        return None

    wanted = '%s/%s' % (target['folder'], target['skeleton'])
    current = skeleton.get_path_name().split('.')[0]
    if current == wanted:
        return skeleton
    if u.EditorAssetLibrary.rename_asset(current, wanted):
        return u.EditorAssetLibrary.load_asset(wanted)
    warnings.append('could not rename skeleton %s to %s' % (current, wanted))
    return skeleton


def normalise_animations(folder, target, warnings):
    """Report imported animations and give them the canonical A_ prefix.

    Animation take names come from the FBX and are not fully under our control,
    so this only rewrites names that carry the mesh prefix and records the rest
    rather than inventing a mapping.
    """
    found = []
    for path in u.EditorAssetLibrary.list_assets(folder, recursive=False):
        asset_path = path.split('.')[0]
        asset = u.EditorAssetLibrary.load_asset(asset_path)
        if not isinstance(asset, u.AnimSequence):
            continue
        name = asset.get_name()
        if name.startswith(target['anim_prefix']):
            found.append(asset_path)
            continue
        suffix = name
        mesh_prefix = target['mesh'] + '_'
        if suffix.startswith(mesh_prefix):
            suffix = suffix[len(mesh_prefix):]
        wanted = '%s/%s%s' % (folder, target['anim_prefix'], suffix)
        if u.EditorAssetLibrary.rename_asset(asset_path, wanted):
            found.append(wanted)
        else:
            warnings.append('could not rename animation %s to %s' % (asset_path, wanted))
            found.append(asset_path)
    return found


def ensure_anim_blueprint(skeleton, target, warnings):
    """Best-effort empty AnimBlueprint bound to the skeleton.

    Deliberately non-fatal and explicitly reported: a factory signature that moved
    between versions must not fail an import whose real job is the mesh. The
    result has no state machine - the gameplay states are wired later.
    """
    if skeleton is None:
        return None, 'no skeleton'
    wanted = '%s/%s' % (target['folder'], target['anim_blueprint'])
    if u.EditorAssetLibrary.does_asset_exist(wanted):
        return wanted, 'already present'
    factory = getattr(u, 'AnimBlueprintFactory', None)
    if factory is None:
        return None, 'AnimBlueprintFactory is not exposed in this build'
    try:
        new_factory = factory()
        new_factory.set_editor_property('target_skeleton', skeleton)
        created = u.AssetToolsHelpers.get_asset_tools().create_asset(
            target['anim_blueprint'], target['folder'], u.AnimBlueprint, new_factory)
        if created is None:
            return None, 'create_asset returned nothing'
        return created.get_path_name().split('.')[0], 'created (empty, no state machine yet)'
    except Exception as exc:
        warnings.append('AnimBlueprint %s not created: %s' % (target['anim_blueprint'], exc))
        return None, str(exc)


def import_character(target, export_root, warnings):
    mesh = import_mesh(target, export_root, warnings)
    height, accessor = measure_height_cm(mesh, warnings)

    asset = {
        'mesh': mesh.get_path_name().split('.')[0],
        'expected_height_cm': target['height_cm'],
        'measured_height_cm': height,
        'measured_with': accessor,
        'tolerance_cm': TOLERANCE_CM,
    }

    # The assertion this script exists for. A None height is a failure too: an
    # unmeasurable mesh cannot be declared correctly scaled.
    if height is None:
        asset['height_ok'] = False
        asset['height_error'] = 'could not measure the mesh bounds'
    else:
        delta = abs(height - target['height_cm'])
        asset['height_delta_cm'] = delta
        asset['height_ok'] = delta <= TOLERANCE_CM
        if not asset['height_ok']:
            asset['height_error'] = (
                'measured %.3f cm, expected %.3f cm +-%.1f cm; check the Blender '
                'export scale (global_scale=100) and the FBX unit setting'
                % (height, target['height_cm'], TOLERANCE_CM))

    skeleton = rename_skeleton(mesh, target, warnings)
    asset['skeleton'] = skeleton.get_path_name().split('.')[0] if skeleton else None
    asset['animations'] = normalise_animations(target['folder'], target, warnings)
    abp, abp_note = ensure_anim_blueprint(skeleton, target, warnings)
    asset['anim_blueprint'] = abp
    asset['anim_blueprint_note'] = abp_note

    u.EditorAssetLibrary.save_asset(asset['mesh'])
    if asset['skeleton']:
        u.EditorAssetLibrary.save_asset(asset['skeleton'])
    return asset


def main():
    warnings = []
    report = {'mode': 'import Blender character FBX as skeletal assets'}

    export_root = find_export_dir(warnings)
    report['export_dir'] = str(export_root)
    report['targets'] = [t['file'] for t in TARGETS]

    assets = []
    for target in TARGETS:
        assets.append(import_character(target, export_root, warnings))
    report['assets'] = assets

    failures = [a for a in assets if not a.get('height_ok')]
    report['scale_assertion_passed'] = not failures
    report['warnings'] = warnings

    out = Path(u.Paths.project_saved_dir()) / 'SceneReports'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'import_art_report.json').write_text(
        json.dumps(report, indent=2), encoding='utf-8')

    for warning in warnings:
        u.log_warning('STAR_IMPORT_ART: ' + warning)
    u.log('STAR_IMPORT_ART_OK ' + json.dumps(report))

    # Reported after the file is written so the report always explains the failure.
    if failures:
        raise RuntimeError(
            'scale assertion failed for: '
            + ', '.join(a['mesh'] for a in failures)
            + '. See import_art_report.json')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Log before re-raising: the commandlet log is the only place an
        # unattended run can explain itself.
        u.log_error('STAR_IMPORT_ART_FAILED\n' + traceback.format_exc())
        raise

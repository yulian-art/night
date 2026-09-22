"""Run inside the UE Python commandlet; report real asset sizes before layout."""
import json
from pathlib import Path
import unreal

registry = unreal.AssetRegistryHelpers.get_asset_registry()
registry.search_all_assets(True)
meshes = []
for data in registry.get_assets_by_path('/Game/LP_sci_fi_island', recursive=True):
    if str(data.asset_class_path.asset_name) != 'StaticMesh':
        continue
    mesh = data.get_asset()
    box = mesh.get_bounding_box()
    meshes.append({
        'path': mesh.get_path_name(),
        'min': [box.min.x, box.min.y, box.min.z],
        'max': [box.max.x, box.max.y, box.max.z],
        'materials': [str(m.material_interface.get_path_name()) if m.material_interface else None
                      for m in mesh.static_materials],
    })
out = Path(unreal.Paths.project_saved_dir()) / 'SceneReports'
out.mkdir(parents=True, exist_ok=True)
(out / 'asset_inventory.json').write_text(json.dumps(meshes, indent=2), encoding='utf-8')
unreal.log('STAR_ASSET_INSPECTION_OK: %d static meshes' % len(meshes))

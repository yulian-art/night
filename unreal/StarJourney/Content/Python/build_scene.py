"""Build a native, editable UE scene and a 30-second Sequencer visual prototype.

Run through Manage-StarJourney.ps1. Only /Game/StarJourney is generated.
This is a cinematic scene study, not the gesture-input gameplay implementation.
"""
import json
import math
from pathlib import Path
import random
import unreal as u

ROOT = '/Game/StarJourney'
MAP = ROOT + '/Maps/L_EchoForest'
FPS, DURATION = 30, 30
END = FPS * DURATION
RNG = random.Random(731)
ASSETS = u.AssetToolsHelpers.get_asset_tools()
ACTORS = u.get_editor_subsystem(u.EditorActorSubsystem)
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
MEL = u.MaterialEditingLibrary
MESHES = {}
MATERIALS = {}
ANIMATED = []
STATIONS = []
MOVERS = []


def color(hex_value):
    """Convert design sRGB colors to UE linear space."""
    raw = [int(hex_value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in raw]
    return u.LinearColor(*linear, 1)


def expression(mat, cls, **props):
    node = MEL.create_material_expression(mat, cls)
    for key, value in props.items():
        node.set_editor_property(key, value)
    return node


def material(name, hex_value, emission=0, unlit=False):
    path = ROOT + '/Materials/' + name
    mat = u.load_asset(path) if u.EditorAssetLibrary.does_asset_exist(path) else ASSETS.create_asset(
        name, ROOT + '/Materials', u.Material, u.MaterialFactoryNew())
    MEL.delete_all_material_expressions(mat)
    if unlit:
        mat.set_editor_property('shading_model', u.MaterialShadingModel.MSM_UNLIT)
    rgb = color(hex_value)
    base = expression(mat, u.MaterialExpressionConstant3Vector, constant=rgb)
    MEL.connect_material_property(base, '', u.MaterialProperty.MP_BASE_COLOR)
    rough = expression(mat, u.MaterialExpressionConstant, r=.88)
    MEL.connect_material_property(rough, '', u.MaterialProperty.MP_ROUGHNESS)
    if emission or unlit:
        power = max(emission, 1 if unlit else 0)
        glow = expression(mat, u.MaterialExpressionConstant3Vector,
                          constant=u.LinearColor(rgb.r * power, rgb.g * power, rgb.b * power, 1))
        MEL.connect_material_property(glow, '', u.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(mat)
    MATERIALS[name] = mat
    return mat


def custom_material(name, code, input_cls, input_name, sky=False, masked=False):
    mat = material(name, 'FFFFFF', unlit=True)
    MEL.delete_all_material_expressions(mat)
    mat.set_editor_property('two_sided', True)
    mat.set_editor_property('is_sky', sky)
    source = expression(mat, input_cls)
    custom_input = u.CustomInput()
    custom_input.set_editor_property('input_name', input_name)
    custom = expression(mat, u.MaterialExpressionCustom, code=code,
                        output_type=u.CustomMaterialOutputType.CMOT_FLOAT4 if masked else u.CustomMaterialOutputType.CMOT_FLOAT3,
                        inputs=[custom_input])
    MEL.connect_material_expressions(source, '', custom, input_name)
    MEL.connect_material_property(custom, '', u.MaterialProperty.MP_EMISSIVE_COLOR)
    if masked:
        mat.set_editor_property('blend_mode', u.BlendMode.BLEND_MASKED)
        mat.set_editor_property('opacity_mask_clip_value', .001)
        alpha = expression(mat, u.MaterialExpressionComponentMask, r=False, g=False, b=False, a=True)
        if not MEL.connect_material_expressions(custom, '', alpha, ''):
            raise RuntimeError('Cannot connect planet opacity mask')
        MEL.connect_material_property(alpha, '', u.MaterialProperty.MP_OPACITY_MASK)
    MEL.recompile_material(mat)
    return mat


def mesh_asset(name):
    if name not in MESHES:
        path = '/Engine/BasicShapes/' + name if name in ('Cube', 'Sphere', 'Cylinder', 'Cone', 'Plane') else (
            '/Game/LP_sci_fi_island/Meshes/Interiors/SM_interiors_island_' + name)
        MESHES[name] = u.load_asset(path)
        if not MESHES[name]:
            raise RuntimeError('Required mesh missing: ' + path)
    return MESHES[name]


def spawn(cls, name, pos, folder, rotation=(0, 0, 0)):
    actor = ACTORS.spawn_actor_from_class(cls, u.Vector(*pos), u.Rotator(*rotation))
    actor.set_actor_label(name)
    actor.set_folder_path(folder)
    return actor


def mesh(name, asset, pos, scale=(1, 1, 1), mat=None, folder='02_Environment', rotation=(0, 0, 0), moving=False):
    actor = spawn(u.StaticMeshActor, name, pos, folder, rotation)
    comp = actor.static_mesh_component
    comp.set_mobility(u.ComponentMobility.MOVABLE if moving else u.ComponentMobility.STATIC)
    comp.set_static_mesh(mesh_asset(asset))
    actor.set_actor_scale3d(u.Vector(*scale))
    if mat:
        for index in range(comp.get_num_materials()):
            comp.set_material(index, MATERIALS[mat] if isinstance(mat, str) else mat)
    if folder.startswith(('00_', '06_', '07_')):
        comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        comp.set_cast_shadow(False)
    return actor


def prop(name, asset, xy, height, z=0, mat=None, folder='02_Environment', yaw=0):
    bounds = mesh_asset(asset).get_bounding_box()
    s = height / (bounds.max.z - bounds.min.z)
    center_x = (bounds.max.x + bounds.min.x) * .5 * s
    center_y = (bounds.max.y + bounds.min.y) * .5 * s
    angle = math.radians(yaw)
    pos = (xy[0] - center_x * math.cos(angle) + center_y * math.sin(angle),
           xy[1] - center_x * math.sin(angle) - center_y * math.cos(angle), z - bounds.min.z * s)
    return mesh(name, asset, pos, (s, s, s), mat, folder, (0, yaw, 0))


def lamp(name, pos, intensity, tint='FFD18C', radius=700):
    actor = spawn(u.PointLight, name, pos, '04_Lighting')
    comp = actor.point_light_component
    comp.set_mobility(u.ComponentMobility.MOVABLE)
    comp.set_light_color(color(tint))
    comp.set_intensity(intensity)
    comp.set_editor_property('attenuation_radius', radius)
    comp.set_editor_property('cast_shadows', False)
    comp.set_editor_property('source_radius', 35)
    return actor


def transform_track(sequence, actor, samples):
    binding = sequence.add_possessable(actor)
    track = binding.add_track(u.MovieScene3DTransformTrack)
    section = track.add_section()
    section.set_range(0, END + 1)
    channels = section.get_all_channels()
    for frame, pos, rotation, scale in samples:
        # Transform channel rotation order is Roll, Pitch, Yaw.
        values = (*pos, rotation[2], rotation[0], rotation[1], *scale)
        for channel, value in zip(channels, values):
            channel.add_key(u.FrameNumber(frame), float(value), interpolation=u.MovieSceneKeyInterpolation.LINEAR)
    return binding


def float_track(sequence, obj, property_name, samples):
    binding = sequence.add_possessable(obj)
    track = binding.add_track(u.MovieSceneFloatTrack)
    track.set_property_name_and_path(property_name, property_name)
    section = track.add_section()
    section.set_range(0, END + 1)
    channel = section.get_all_channels()[0]
    for frame, value in samples:
        channel.add_key(u.FrameNumber(frame), value, interpolation=u.MovieSceneKeyInterpolation.LINEAR)


def journey(t):
    points = [(0, 0), (5, 1800), (7, 1800), (14, 5200), (16, 5200),
              (23, 8700), (25, 8700), (30, 10400)]
    for (a, x), (b, y) in zip(points, points[1:]):
        if t <= b:
            return x + (y - x) * max(0, (t - a) / (b - a)), y != x
    return 10400, False


def lane(t):
    if 2 <= t < 2.45:
        return -180 * (t - 2) / .45
    if 2.45 <= t < 3.6:
        return -180
    if 3.6 <= t < 4.05:
        return -180 * (1 - (t - 3.6) / .45)
    return 0


def jump(t):
    for start in (2, 3.6, 5.5, 14.5, 23.5):
        if start <= t <= start + .7:
            return math.sin((t - start) / .7 * math.pi) * 65
    return 0


def make_materials():
    for name, hex_value, power in [
        ('Road', '354856', .05), ('RoadAlternate', '394D5B', .05), ('Stone', '243341', .1),
        ('Moss', '294D50', .1), ('MossLight', '426763', .12), ('Bark', '283841', .1),
        ('TealTree', '326C70', .2), ('DeepTree', '25535E', .2), ('PaleTree', '638F8C', .12),
        ('Line', '659397', .35), ('Gold', 'FFD18C', 1.4), ('DimGold', 'B8864E', .4),
        ('Cyan', '7CBAB7', .6), ('Suit', 'E0E8E6', .13), ('Visor', '1B354B', .15),
        ('Pack', '506F7B', .1), ('Scarf', 'EFAF66', .2), ('Fox', 'D89057', .15),
        ('FoxCream', 'FFDFAD', .2), ('Black', '112434', .02), ('Star', 'FFDBA0', 4),
        ('FarMountain', '426579', .8), ('MidMountain', '304F64', .6), ('NearMountain', '243F52', .5),
    ]:
        material(name, hex_value, power)
    custom_material('Sky', r'''
float3 d = normalize(P);
float h = saturate(d.z);
float3 horizon = float3(0.055, 0.105, 0.155);
float3 upper = float3(0.004, 0.010, 0.033);
float3 sky = lerp(horizon, upper, smoothstep(0.0, 0.38, h));
sky += float3(0.032, 0.022, 0.018) * exp(-abs(d.z - 0.018) * 22);
float2 uv = float2(atan2(d.y,d.x), asin(d.z)) * float2(100,100);
float2 cell = floor(uv);
float seed = frac(sin(dot(cell, float2(127.1,311.7))) * 43758.5453);
float2 offset = float2(seed, frac(seed * 31.7));
float star = (1 - smoothstep(0.018, 0.065, length(frac(uv)-offset))) * step(0.93,seed);
return sky + star * float3(1.0,0.84,0.61) * smoothstep(0.04,0.3,h);
''', u.MaterialExpressionWorldPosition, 'P', sky=True)
    custom_material('Planet', r'''
float2 p = (UV.yx - 0.5) * 2;
float rr = dot(p,p);
float3 n = float3(p,sqrt(saturate(1-rr)));
float lit = saturate(dot(n,normalize(float3(-0.6,0.15,0.7))));
float bands = sin((p.y+p.x*0.18)*24 + sin(p.x*8)*0.7)*0.5+0.5;
float3 sea = lerp(float3(0.018,0.046,0.085),float3(0.11,0.19,0.23),lit);
sea *= 0.92 + bands*0.08;
float rim = pow(1-n.z,4);
return float4(sea + rim*float3(0.12,0.19,0.20), 1-rr);
''', u.MaterialExpressionTextureCoordinate, 'UV', masked=True)


def make_world():
    mesh('Gradient star sky', 'Sphere', (0, 0, 0), (4000, 4000, 4000), 'Sky', '00_Sky')
    mesh('Giant quiet planet', 'Plane', (57000, 10000, 32500), (750, 750, 1), 'Planet', '00_Sky', (90, 0, 0))
    # Three separate silhouette layers with controlled values.
    for layer, (distance, z, height, mat) in enumerate([
        (49000, -3900, 10500, 'FarMountain'), (35500, -3200, 6600, 'MidMountain'),
        (24000, -2600, 3500, 'NearMountain')]):
        for index in range(19):
            y = (index - 9) * distance * .12
            h = height * RNG.uniform(.65, 1.3)
            mesh('Ridge %d %02d' % (layer, index), 'Cone',
                 (distance + RNG.uniform(-1800, 1800), y, z),
                 (h * .008, h * RNG.uniform(.027, .052), h * .01), mat, '00_Backdrop')
    for index, (x, y, z, s) in enumerate([(17000, -6000, 500, .16), (24500, 8400, 1700, .2),
                                          (32000, -10500, 2400, .13), (19000, 11500, -300, .12)]):
        prop('Floating island %02d' % index, 'Island1', (x, y), 8112 * s, z=z - 8112 * s,
             mat='MidMountain', folder='00_Backdrop', yaw=index * 53)
        prop('Island grove %02d' % index, 'Trees', (x, y), 800 * s * 4, z=z,
             mat='PaleTree', folder='00_Backdrop')
    for index in range(40):
        x = -1800 + index * 360
        mesh('Causeway slab %02d' % index, 'Cube', (x, 0, -35), (3.58, 6.6, .7),
             'Road' if index % 2 else 'RoadAlternate', '01_Road')
        for y in (-335, 335):
            mesh('Border %02d %d' % (index, y), 'Cube', (x, y, -6), (3.58, .10, .13),
                 'Line', '01_Road')
        for y in (-90, 90):
            mesh('Lane dash %02d %d' % (index, y), 'Cube', (x, y, .5), (.75, .018, .012),
                 'Line', '01_Road')
        if index % 3 == 0:
            for y in (-323, 323):
                mesh('Edge beacon %d %d' % (index, y), 'Sphere', (x, y, 10), (.075, .075, .075),
                     'Gold', '01_Road')
    # Groves sit on small terraced islands beside the route.
    for index in range(36):
        x = -650 + index * 370
        side = -1 if index % 2 else 1
        y = side * RNG.uniform(580, 1050)
        radius = RNG.uniform(3.8, 6.2)
        mesh('Grove terrace %02d' % index, 'Cylinder', (x, y, -68), (radius * 1.5, radius, 1.0),
             'Moss', '02_Environment/Ground')
        mesh('Floating rock %02d' % index, 'Cone', (x, y, -370), (radius * 1.4, radius, 5.5),
             'Stone', '02_Environment/Ground', (180, 0, 0))
        for j in range(3):
            tx, ty = x + RNG.uniform(-200, 200), y + side * RNG.uniform(-120, 200)
            tree_variant = [1, 4, 3][j] if index % 3 else [1, 2, 4][j]
            prop('Canopy %02d %d' % (index, j), 'Tree_' + str(tree_variant), (tx, ty),
                 RNG.uniform(340, 720), z=-12, mat=['TealTree', 'DeepTree', 'PaleTree'][j],
                 folder='02_Environment/Trees', yaw=RNG.uniform(0, 360))
        prop('Crystal cluster %02d' % index, 'Crystal_' + str(2 + index % 4),
             (x + 100, side * RNG.uniform(390, 500)), RNG.uniform(55, 145), z=-6,
             mat='Cyan' if index % 5 == 0 else 'PaleTree', folder='02_Environment/Crystals', yaw=index * 39)
        for j in range(2):
            prop('Mushroom %02d %d' % (index, j), 'Mushroom_' + str(1 + j),
                 (x + RNG.uniform(-200, 200), side * RNG.uniform(370, 600)), RNG.uniform(35, 80),
                 mat='DimGold', folder='02_Environment/Mushrooms', yaw=index * 17)
    for i in range(15):
        prop('Outer grove %02d' % i, 'Trees', (i * 1000, (-1 if i % 2 else 1) * RNG.uniform(1800, 2700)),
             RNG.uniform(950, 1600), z=-180, mat='DeepTree', folder='02_Environment/OuterGroves', yaw=i * 27)
    # An abandoned observatory is a quiet destination landmark.
    prop('Far observatory', 'Planetarium', (12700, -750), 950, z=0,
         mat='PaleTree', folder='02_Environment/Landmark', yaw=90)
    prop('Docked ship', 'Spaceship_1', (11900, 1500), 110, z=340,
         folder='02_Environment/Landmark', yaw=115)
    # A few floating lights describe the route without covering the road.
    for i in range(90):
        x, y, z = RNG.uniform(-500, 13000), RNG.choice([-1, 1]) * RNG.uniform(350, 1300), RNG.uniform(30, 450)
        a = mesh('Drifting seed %03d' % i, 'Sphere', (x, y, z), (.025, .025, .025),
                 'Star', '06_Fireflies', moving=True)
        if i % 3 == 0:
            MOVERS.append((a, 15, i))


def make_stations():
    for index, (x, t) in enumerate(((2200, 6.1), (5600, 15.1), (9100, 24.1))):
        y = -460 if index != 1 else 460
        f = '03_Stations/Station_%02d' % (index + 1)
        mesh('Station %d dais' % index, 'Cylinder', (x, y, -4), (2.6, 2.6, .18), 'MossLight', f)
        prop('Station %d asset lamp' % index, 'Streetlight_1', (x, y), 320, mat='Pack', folder=f)
        mesh('Lantern plinth %d' % index, 'Cylinder', (x, y, 25), (.65, .65, .5), 'Stone', f)
        mesh('Lantern stem %d' % index, 'Cylinder', (x, y, 195), (.095, .095, 3.2), 'Scarf', f)
        for z in (330, 410):
            mesh('Lantern rim %d %d' % (index, z), 'Cylinder', (x, y, z), (.8, .8, .09), 'Scarf', f)
        for dx, dy in ((-28, -28), (-28, 28), (28, -28), (28, 28)):
            mesh('Lantern strut %d %d %d' % (index, dx, dy), 'Cylinder', (x + dx, y + dy, 370),
                 (.035, .035, .8), 'Scarf', f)
        core = mesh('Star lantern %d' % index, 'Sphere', (x, y, 365), (.28, .28, .5), 'Gold', f, moving=True)
        mesh('Lantern crown %d' % index, 'Cone', (x, y, 434), (1.0, 1.0, .4), 'Scarf', f)
        light = lamp('Station %d warm pool' % index, (x - 60, y, 325), 35, radius=950)
        STATIONS.append((core, light, t))
        for j in range(12):
            angle = j * math.tau / 12
            sparkle = mesh('Station %d bloom mote %02d' % (index, j), 'Sphere',
                           (x + 90 * math.cos(angle), y + 90 * math.sin(angle), 80),
                           (.001, .001, .001), 'Star', '06_StationBloom', moving=True)
            ANIMATED.append((sparkle, t, angle))
        for j in range(4):
            prop('Station %d mushroom %d' % (index, j), 'Mushroom_1',
                 (x - 150 + j * 95, y + (-130 if y < 0 else 130)), 55 + j * 7,
                 mat='Gold' if j == 1 else 'DimGold', folder=f)


def make_travellers():
    parts = []

    def part(name, asset, pos, scale, mat, role='', rotation=(0, 0, 0)):
        a = mesh(name, asset, pos, scale, mat, '05_Travellers', rotation, moving=True)
        parts.append((a, tuple(pos), tuple(scale), tuple(rotation), role))
        return a

    # Art placeholders are assembled meshes; every part remains replaceable.
    part('Astronaut | torso', 'Sphere', (0, 0, 86), (.46, .52, .61), 'Suit')
    part('Astronaut | helmet', 'Sphere', (0, 0, 142), (.64, .64, .64), 'Suit')
    part('Astronaut | front visor', 'Sphere', (21, 0, 143), (.3, .54, .45), 'Visor')
    part('Astronaut | life support', 'Cube', (-26, 0, 89), (.29, .39, .49), 'Pack')
    part('Astronaut | oxygen glow', 'Cube', (-42, 0, 90), (.018, .22, .05), 'Gold')
    part('Astronaut | scarf collar', 'Sphere', (0, 0, 113), (.48, .5, .15), 'Scarf')
    part('Astronaut | trailing scarf', 'Cube', (-48, 14, 106), (.6, .16, .05), 'Scarf', 'scarf', (0, 12, 0))
    for side in (-1, 1):
        role = 'left' if side < 0 else 'right'
        part('Astronaut | %s leg' % role, 'Sphere', (0, side * 14, 37), (.20, .21, .55), 'Suit', role + '_leg')
        part('Astronaut | %s boot' % role, 'Sphere', (9, side * 14, 12), (.32, .25, .21), 'Pack', role + '_boot')
        part('Astronaut | %s arm' % role, 'Sphere', (0, side * 34, 84), (.19, .20, .52), 'Suit', role + '_arm')
        part('Astronaut | %s glove' % role, 'Sphere', (0, side * 36, 62), (.21, .21, .22), 'Scarf', role + '_glove')
    fox = (25, 145, 0)
    def foxpart(name, asset, offset, scale, mat, role='fox', rotation=(0, 0, 0)):
        return part('Fox | ' + name, asset, tuple(a+b for a, b in zip(fox, offset)), scale, mat, role, rotation)
    foxpart('body', 'Sphere', (0, 0, 41), (.75, .29, .34), 'Fox')
    foxpart('chest', 'Sphere', (28, 0, 45), (.25, .30, .40), 'FoxCream')
    foxpart('head', 'Sphere', (39, 0, 70), (.40, .34, .37), 'Fox')
    foxpart('muzzle', 'Cone', (62, 0, 65), (.25, .25, .4), 'FoxCream', rotation=(90, 0, 0))
    foxpart('nose', 'Sphere', (81, 0, 65), (.075, .095, .09), 'Black')
    for side in (-1, 1):
        foxpart('ear %d' % side, 'Cone', (37, side * 12, 95), (.15, .18, .36), 'Fox')
        foxpart('eye %d' % side, 'Sphere', (52, side * 13, 74), (.07, .065, .075), 'Black')
        for front in (-1, 1):
            foxpart('paw %d %d' % (side, front), 'Sphere', (front * 24, side * 10, 17),
                    (.12, .13, .31), 'Fox', 'fox_leg_%d' % (side * front))
    foxpart('tail', 'Sphere', (-53, 0, 60), (.67, .23, .24), 'Fox', 'tail', (-22, 0, 0))
    foxpart('tail tip', 'Sphere', (-80, 0, 72), (.27, .23, .24), 'FoxCream', 'tail', (-22, 0, 0))
    return parts


def make_lighting():
    key = spawn(u.DirectionalLight, 'Soft moonlight', (0, 0, 1000), '04_Lighting', (-35, -35, 0))
    key.light_component.set_mobility(u.ComponentMobility.MOVABLE)
    key.light_component.set_intensity(3.5)
    key.light_component.set_light_color(color('BDDFEA'))
    key.light_component.set_editor_property('light_source_angle', 5)
    fill = spawn(u.DirectionalLight, 'Warm horizon fill', (0, 0, 1000), '04_Lighting', (-18, 145, 0))
    fill.light_component.set_mobility(u.ComponentMobility.MOVABLE)
    fill.light_component.set_intensity(1.1)
    fill.light_component.set_light_color(color('FFDCB1'))
    fill.light_component.set_editor_property('cast_shadows', False)
    sky = spawn(u.SkyLight, 'Forest skylight', (0, 0, 1000), '04_Lighting')
    sky.light_component.set_mobility(u.ComponentMobility.MOVABLE)
    sky.light_component.set_intensity(.65)
    sky.light_component.set_editor_property('real_time_capture', True)
    pp = spawn(u.PostProcessVolume, 'Fixed exposure and restrained bloom', (0, 0, 0), '04_Lighting')
    pp.set_editor_property('unbound', True)
    settings = pp.get_editor_property('settings')
    for key, value in {'override_auto_exposure_method': True, 'auto_exposure_method': u.AutoExposureMethod.AEM_MANUAL,
                       'override_auto_exposure_bias': True, 'auto_exposure_bias': 0.0,
                       'override_auto_exposure_apply_physical_camera_exposure': True,
                       'auto_exposure_apply_physical_camera_exposure': False,
                       'override_bloom_intensity': True, 'bloom_intensity': .28,
                       'override_vignette_intensity': True, 'vignette_intensity': .20,
                       'override_motion_blur_amount': True, 'motion_blur_amount': 0.0}.items():
        settings.set_editor_property(key, value)
    pp.set_editor_property('settings', settings)
    return sky


def make_sequence(parts, camera):
    path = ROOT + '/Cinematics/LS_EchoForest_30s'
    if u.EditorAssetLibrary.does_asset_exist(path):
        # Rebuild tracks in place so external references to the sequence survive.
        seq = u.load_asset(path)
        for binding in seq.get_bindings():
            binding.remove()
        for track in seq.get_tracks():
            seq.remove_track(track)
    else:
        seq = ASSETS.create_asset('LS_EchoForest_30s', ROOT + '/Cinematics', u.LevelSequence, u.LevelSequenceFactoryNew())
    seq.set_display_rate(u.FrameRate(FPS, 1))
    seq.set_playback_start(0)
    seq.set_playback_end(END)
    frames = list(range(0, END + 1, 3))
    camera_binding = transform_track(seq, camera, [
        (frame, (journey(frame / FPS)[0] - 1350, 0, 440), (-6, 0, 0), (1, 1, 1)) for frame in frames])
    cuts = seq.add_track(u.MovieSceneCameraCutTrack)
    cut = cuts.add_section()
    cut.set_range(0, END)
    cut.set_camera_binding_id(seq.get_binding_id(camera_binding))
    for actor, origin, scale, rotation, role in parts:
        samples = []
        for frame in frames:
            t = frame / FPS
            x, running = journey(t)
            phase = t * math.tau * 2.6
            is_fox = role.startswith('fox') or role == 'tail'
            side = -1 if role.startswith('left') else 1
            stride = math.sin(phase) * (1 if running else 0)
            bob = abs(math.sin(phase)) * (4 if running else 1)
            ox, oy, oz = origin
            pitch, yaw, roll = rotation
            sx, sy, sz = scale
            if is_fox:
                bob *= .65
                if role.startswith('fox_leg'):
                    ox += stride * (9 if role.endswith('-1') else -9)
                if role == 'tail':
                    yaw += math.sin(t * 3) * 16
                yoff, zoff = lane(t) * .3, bob
            else:
                yoff, zoff = lane(t), bob + jump(t)
                if role.endswith(('leg', 'boot')):
                    ox += side * stride * 16
                    zoff += max(0, side * stride) * 12
                if role.endswith(('arm', 'glove')):
                    ox -= side * stride * 15
                    for start in (5.5, 14.5, 23.5):
                        spread = max(0, math.sin((t - start) / .7 * math.pi)) if start <= t <= start + .7 else 0
                        oy += side * spread * 30
                        oz += spread * 40
                        roll += side * spread * 60
                if 10 <= t <= 11.3:
                    amount = min(1, (t - 10) / .2, (11.3 - t) / .2)
                    zoff -= amount * 32
                    if role.endswith(('leg', 'boot')):
                        zoff += amount * 25
                    else:
                        pitch -= amount * 18
                if role == 'scarf':
                    yaw += math.sin(t * 8) * 14
            samples.append((frame, (x + ox, oy + yoff, oz + zoff), (pitch, yaw, roll), (sx, sy, sz)))
        transform_track(seq, actor, samples)
    for core, light, time in STATIONS:
        p, s = core.get_actor_location(), core.get_actor_scale3d()
        on = round(time * FPS)
        transform_track(seq, core, [
            (0, (p.x, p.y, p.z), (0, 0, 0), (.04, .04, .07)),
            (on, (p.x, p.y, p.z), (0, 0, 0), (.04, .04, .07)),
            (on + 12, (p.x, p.y, p.z), (0, 0, 0), (s.x * 1.2, s.y * 1.2, s.z * 1.2)),
            (on + 30, (p.x, p.y, p.z), (0, 0, 0), (s.x, s.y, s.z)),
            (END, (p.x, p.y, p.z), (0, 0, 0), (s.x, s.y, s.z))])
        float_track(seq, light.point_light_component, 'Intensity', [(0, 5.0), (on, 5.0), (on + 24, 240.0), (END, 240.0)])
    for sparkle, t, angle in ANIMATED:
        p = sparkle.get_actor_location()
        f = round(t * FPS)
        transform_track(seq, sparkle, [
            (0, (p.x, p.y, p.z), (0, 0, 0), (.001, .001, .001)),
            (f, (p.x, p.y, p.z), (0, 0, 0), (.001, .001, .001)),
            (f + 7, (p.x, p.y, p.z + 40), (0, 0, 0), (.05, .05, .05)),
            (f + 36, (p.x + 75 * math.cos(angle), p.y + 75 * math.sin(angle), p.z + 300), (0, 0, 0), (.015, .015, .015)),
            (f + 45, (p.x, p.y, p.z + 330), (0, 0, 0), (.001, .001, .001)),
            (END, (p.x, p.y, p.z + 330), (0, 0, 0), (.001, .001, .001))])
    for actor, amplitude, phase in MOVERS:
        p, s = actor.get_actor_location(), actor.get_actor_scale3d()
        transform_track(seq, actor, [(frame, (p.x, p.y + math.sin(frame / 50 + phase) * amplitude,
                                            p.z + math.sin(frame / 38 + phase) * amplitude),
                                      (0, 0, 0), (s.x, s.y, s.z)) for frame in range(0, END + 1, 15)])
    director = spawn(u.LevelSequenceActor, 'PLAY | Echo Forest 30 second loop', (0, 0, 0), '07_Director')
    director.set_sequence(seq)
    settings = director.get_editor_property('playback_settings')
    settings.set_editor_property('auto_play', True)
    settings.set_editor_property('loop_count', u.MovieSceneSequenceLoopCount(value=-1))
    settings.set_editor_property('hide_hud', True)
    settings.set_editor_property('hide_player', True)
    settings.set_editor_property('disable_movement_input', True)
    settings.set_editor_property('disable_look_at_input', True)
    director.set_editor_property('playback_settings', settings)
    return seq


def main():
    registry = u.AssetRegistryHelpers.get_asset_registry()
    registry.search_all_assets(True)
    if u.EditorAssetLibrary.does_asset_exist(MAP):
        if not LEVEL.load_level(MAP):
            raise RuntimeError('Could not load map ' + MAP)
        for actor in ACTORS.get_all_level_actors():
            if str(actor.get_folder_path()).startswith(tuple('%02d_' % i for i in range(8))):
                ACTORS.destroy_actor(actor)
    elif not LEVEL.new_level(MAP):
        raise RuntimeError('Could not create map ' + MAP)
    make_materials()
    make_world()
    make_stations()
    parts = make_travellers()
    make_lighting()
    camera = spawn(u.CameraActor, 'CAM | Fixed rear view', (-1350, 0, 440), '07_Director', (-6, 0, 0))
    camera.camera_component.set_field_of_view(55)
    camera.camera_component.set_editor_property('aspect_ratio', 16 / 9)
    camera.camera_component.set_editor_property('constrain_aspect_ratio', True)
    camera.set_editor_property('auto_activate_for_player', u.AutoReceiveInput.PLAYER0)
    sequence = make_sequence(parts, camera)
    u.get_editor_subsystem(u.UnrealEditorSubsystem).set_level_viewport_camera_info(camera.get_actor_location(), camera.get_actor_rotation())
    if not LEVEL.save_current_level():
        raise RuntimeError('Failed to save generated map')
    if not u.EditorAssetLibrary.save_directory(ROOT, only_if_is_dirty=False, recursive=True):
        raise RuntimeError('Failed to save generated assets')
    actors = ACTORS.get_all_level_actors()
    report = {
        'map': MAP, 'sequence': sequence.get_path_name(), 'duration_seconds': DURATION,
        'actors': len(actors), 'source_meshes_used': sorted(MESHES), 'station_count': len(STATIONS),
        'sequence_bindings': len(sequence.get_bindings()),
        'camera_cuts': len([t for t in sequence.get_tracks() if isinstance(t, u.MovieSceneCameraCutTrack)]),
        'mode': 'cinematic scene prototype; no gesture input or save writes',
    }
    out = Path(u.Paths.project_saved_dir()) / 'SceneReports'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'build_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    u.log('STAR_SCENE_BUILD_OK ' + json.dumps(report))


if __name__ == '__main__':
    main()

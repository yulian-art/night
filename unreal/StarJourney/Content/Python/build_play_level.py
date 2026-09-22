"""Fork the cinematic Echo Forest map into a playable map and point the engine at it.

Run through Manage-StarJourney.ps1 -Action PlayLevel. Only /Game/StarJourney is
written; the movie map keeps its scenery, its lights and its Sequencer intact.

Why a second map instead of editing the movie: the cinematic drives every actor
from a 30-second Level Sequence while the game drives characters from a Pawn. In
one map the two fight - the timeline keeps moving actors the player is supposed to
control, and the GameMode spawns a runner inside a movie. So the scenery is copied
once and only the movie-only actors are stripped from the copy.

Why the GameMode override is set on BOTH maps: DefaultEngine.ini now makes the
gameplay mode the global default, and a map with no explicit override inherits it.
Without pinning the movie map back to GameModeBase it would start spawning the
playable Pawn over the demo. That single property is the only thing this script
changes on the cinematic map.
"""
import json
from pathlib import Path
import traceback
import unreal as u

ROOT = '/Game/StarJourney'
CINE_MAP = ROOT + '/Maps/L_EchoForest'
PLAY_MAP = ROOT + '/Maps/L_EchoForest_Play'
SCRIPTS = '/Script/StarJourney'

# Actors that only make sense in the movie and must not exist in a playable map.
DIRECTOR_LABEL = 'PLAY | Echo Forest 30 second loop'
CINE_CAMERA_LABEL = 'CAM | Fixed rear view'
TRAVELLER_FOLDER = '05_Travellers'
STATION_FOLDER = '03_Stations'

# Level 2 (回声森林) has three lamps and each is lit by one complete jumping jack,
# matching the movie's three light-up moments (6.1 / 15.1 / 24.1 s). The X values
# are the station positions build_scene.make_stations placed. journey() ends at
# x = 10400, so that is where the level settles.
STATIONS = ((2200.0, -460.0), (5600.0, 460.0), (9100.0, -460.0))
LEVEL_ID = 2
FINISH_X = 10400.0
# The runner capsule is 90 half-height; lift the spawn clear of the road surface.
PLAYER_START = (0.0, 0.0, 120.0)

LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
ACTORS = u.get_editor_subsystem(u.EditorActorSubsystem)


def actor_label(actor):
    """A readable name for logs and reports, tolerant of odd actors."""
    try:
        return str(actor.get_actor_label())
    except Exception:
        return ''


def folder_path(actor):
    """Folder path for a level actor, or an empty string when unavailable."""
    try:
        return str(actor.get_folder_path())
    except Exception:
        return ''


def property_snake(name):
    """PascalCase -> snake_case, the two spellings set_editor_property accepts.

    StopX -> stop_x. Builds differ in which spelling they take, and a silently
    unset StopX would leave a task point at the world origin.
    """
    out = []
    for index, char in enumerate(name):
        if char.isupper() and index:
            out.append('_')
        out.append(char.lower())
    return ''.join(out)


def property_candidates(name):
    """Every spelling the Python binding may accept for one editor property.

    UPROPERTY names are exposed snake_cased, and a boolean additionally loses its
    leading b: bAutoInitialize -> auto_initialize, StopX -> stop_x. Trying each
    spelling keeps a wrong guess from silently leaving a property unset.
    """
    candidates = [name, property_snake(name)]
    if len(name) > 1 and name[0] == 'b' and name[1].isupper():
        candidates.append(property_snake(name[1:]))
    return candidates


def resolve_class(python_name, script_path, warnings):
    """Resolve a C++ class by binding name, then by script path.

    A class that is not exposed under its friendly name is still reachable through
    its /Script path, and binding names move between engine versions. Failing here
    means the C++ module is not compiled into the project, which is worth a hard
    error rather than an empty map.
    """
    cls = getattr(u, python_name, None)
    if cls is not None:
        return cls
    try:
        cls = u.load_class(None, script_path)
    except Exception as exc:
        warnings.append('load_class(%s) failed: %r' % (script_path, exc))
        cls = None
    if cls is None:
        raise RuntimeError(
            'cannot resolve %s (%s); is the StarJourney C++ module compiled into this project?'
            % (python_name, script_path))
    return cls


def resolve_enum_value(enum_name, candidates, script_paths, warnings):
    """Return the first enum member that exists, trying every known spelling.

    A wrong guess here would place a task station that can never be lit, and the
    failure would only show up as a station that ignores the player, so a total
    miss is a hard error instead of a guess.
    """
    enum = getattr(u, enum_name, None)
    if enum is None:
        for script_path in script_paths:
            try:
                enum = u.load_object(None, script_path)
            except Exception as exc:
                warnings.append('load_object(%s) failed: %r' % (script_path, exc))
                enum = None
            if enum is not None:
                break
    if enum is None:
        raise RuntimeError('cannot resolve enum %s (%s)' % (enum_name, list(script_paths)))
    for candidate in candidates:
        value = getattr(enum, candidate, None)
        if value is not None:
            return value
    raise RuntimeError('enum %s exposes none of %s' % (enum_name, list(candidates)))


def set_property(actor, name, value, warnings):
    """Set an editor property, tolerating either spelling. Returns success."""
    last = None
    for candidate in property_candidates(name):
        try:
            actor.set_editor_property(candidate, value)
            return True
        except Exception as exc:
            last = exc
    warnings.append('could not set %s on %s: %r' % (name, actor_label(actor), last))
    return False


def probe_property(actor, name):
    """Report whether an editor property is exposed, and its current value.

    Used for the director's auto-initialize flag: the play map relies on it to
    wire the run without a level Blueprint, so the report should say plainly
    whether it is there.
    """
    for candidate in property_candidates(name):
        try:
            return candidate, bool(actor.get_editor_property(candidate))
        except Exception:
            continue
    return None, None


def world_settings(actors):
    """The level's WorldSettings actor, or None.

    The per-map GameMode override lives on this actor and has no ini equivalent,
    so reaching it is the only way to pin a single map's mode.
    """
    for actor in actors:
        if isinstance(actor, u.WorldSettings):
            return actor
    return None


def set_map_game_mode(actors, mode_class, warnings):
    """Pin one map's GameMode override and verify it took. Returns bool."""
    settings = world_settings(actors)
    if settings is None:
        warnings.append('WorldSettings actor not found; this map will inherit the global game mode')
        return False
    if not mode_class:
        warnings.append('game mode class unavailable; cannot set the override')
        return False
    if not set_property(settings, 'DefaultGameMode', mode_class, warnings):
        return False
    # Read back: the write can appear to succeed while the property stays null.
    try:
        return bool(settings.get_editor_property('default_game_mode'))
    except Exception as exc:
        warnings.append('could not read back DefaultGameMode: %r' % (exc,))
        return True


def load_map(path):
    if not LEVEL.load_level(path):
        raise RuntimeError('could not load map ' + path)
    return ACTORS.get_all_level_actors()


def make_play_map(warnings):
    """Create PLAY_MAP as a fresh copy of CINE_MAP. Returns how it was created.

    duplicate_asset is the direct route, but some builds refuse to duplicate a
    level that is currently loaded, so fall back to the editor's canonical
    "save current level as", which forks the map in place.
    """
    if not u.EditorAssetLibrary.does_asset_exist(CINE_MAP):
        raise RuntimeError('cinematic map missing: ' + CINE_MAP
                           + '; run Manage-StarJourney.ps1 -Action Build first')
    if u.EditorAssetLibrary.does_asset_exist(PLAY_MAP):
        if not u.EditorAssetLibrary.delete_asset(PLAY_MAP):
            raise RuntimeError('could not delete the existing play map: ' + PLAY_MAP)

    try:
        created = u.EditorAssetLibrary.duplicate_asset(CINE_MAP, PLAY_MAP)
        if created:
            return 'duplicate_asset'
        warnings.append('duplicate_asset returned nothing; falling back to save_current_level_as')
    except Exception as exc:
        warnings.append('duplicate_asset failed (%r); falling back to save_current_level_as' % (exc,))

    if not LEVEL.load_level(CINE_MAP):
        raise RuntimeError('could not load the cinematic map: ' + CINE_MAP)
    if not LEVEL.save_current_level_as(PLAY_MAP):
        raise RuntimeError('could not fork the cinematic map into ' + PLAY_MAP)
    return 'save_current_level_as'


def is_cinematic_only(actor):
    """True for actors that exist only to drive the 30-second movie."""
    if actor_label(actor) in (DIRECTOR_LABEL, CINE_CAMERA_LABEL):
        return True
    return folder_path(actor).startswith(TRAVELLER_FOLDER)


def is_previous_output(actor):
    """True for actors a previous PlayLevel run left in the map.

    The map is recreated from scratch each run, so this is insurance: it keeps the
    action idempotent even if the fork route reuses an existing map.
    """
    label = actor_label(actor)
    return label == 'PlayerStart | Echo Forest' or (
        label.startswith('Station ') and label.endswith('task')) or label == 'Director | Echo Forest'


def strip_cinematic_actors(warnings):
    """Remove movie-only actors (and any previous output) from the play map.

    The Sequence director would keep driving the scene from its timeline, the
    authored camera would fight the Pawn's own camera and be left behind as the
    runner advances, and the assembled traveller meshes would duplicate the player.
    A missing target is warned about rather than passed over: a stray director or
    camera is invisible until the game misbehaves.
    """
    removed = []
    stale = 0
    doomed = []
    for actor in list(ACTORS.get_all_level_actors()):
        if is_cinematic_only(actor):
            removed.append({'label': actor_label(actor), 'folder': folder_path(actor),
                            'reason': 'movie-only'})
            doomed.append(actor)
        elif is_previous_output(actor):
            stale += 1
            doomed.append(actor)
    for actor in doomed:
        ACTORS.destroy_actor(actor)

    reasons = {item['label'] for item in removed}
    if DIRECTOR_LABEL not in reasons:
        warnings.append('no actor labelled %r found; the copy may already be clean' % DIRECTOR_LABEL)
    if CINE_CAMERA_LABEL not in reasons:
        warnings.append('no actor labelled %r found; check the copy for a stray camera' % CINE_CAMERA_LABEL)
    return removed, stale


def spawn(cls, label, pos, folder):
    actor = ACTORS.spawn_actor_from_class(cls, u.Vector(*pos), u.Rotator(0, 0, 0))
    actor.set_actor_label(label)
    actor.set_folder_path(folder)
    return actor


def place_gameplay(warnings):
    """Place the PlayerStart, the three task stations and the level director.

    The stations carry no mesh on purpose: the visible lamp, dais and mushrooms
    already exist in the copied scenery, and AStarStation is only the interaction
    trigger. The director keeps its default auto-initialize, so it finds the runner
    and the stations itself and this map needs no Blueprint wiring - which matters
    because Blueprints are binary assets that cannot be authored in this repo.
    """
    station_class = resolve_class('StarStation', SCRIPTS + '.StarStation', warnings)
    director_class = resolve_class('StarLevelDirector', SCRIPTS + '.StarLevelDirector', warnings)
    jumping_jack = resolve_enum_value(
        'StarAction', ('JUMPING_JACK', 'JumpingJack', 'Jumping_Jack'),
        (SCRIPTS + '.EStarAction', SCRIPTS + '.StarAction'), warnings)

    placed = []
    station_errors = []

    start = spawn(u.PlayerStart, 'PlayerStart | Echo Forest', PLAYER_START, STATION_FOLDER)
    placed.append({'class': 'PlayerStart', 'label': actor_label(start),
                   'location': list(PLAYER_START)})

    for index, (x, y) in enumerate(STATIONS, start=1):
        label = 'Station %02d task' % index
        station = spawn(station_class, label, (x, y, 0.0), STATION_FOLDER)
        if not set_property(station, 'StopX', float(x), warnings):
            station_errors.append(label + '.StopX')
        if not set_property(station, 'RequiredSteps', [jumping_jack], warnings):
            station_errors.append(label + '.RequiredSteps')
        placed.append({'class': 'StarStation', 'label': label, 'location': [x, y, 0.0]})

    director = spawn(director_class, 'Director | Echo Forest', (0.0, 0.0, 0.0), STATION_FOLDER)
    set_property(director, 'LevelId', LEVEL_ID, warnings)
    set_property(director, 'FinishX', FINISH_X, warnings)
    placed.append({'class': 'StarLevelDirector', 'label': actor_label(director),
                   'location': [0.0, 0.0, 0.0]})
    return placed, station_errors, director


def main():
    warnings = []
    report = {'mode': 'playable map; cinematic scenery reused, movie actors removed'}

    # Pin the movie map FIRST: the global default is about to become the gameplay
    # mode, and a map without an explicit override would inherit it and spawn the
    # playable Pawn over the demo.
    cine_mode = resolve_class('GameModeBase', '/Script/Engine.GameModeBase', warnings)
    report['cinematic_gamemode_set'] = set_map_game_mode(load_map(CINE_MAP), cine_mode, warnings)
    if not LEVEL.save_current_level():
        raise RuntimeError('could not save the cinematic map')

    report['cinematic_map'] = CINE_MAP
    report['map'] = PLAY_MAP
    report['play_map_created_by'] = make_play_map(warnings)

    play_actors = load_map(PLAY_MAP)
    removed, stale = strip_cinematic_actors(warnings)
    report['removed'] = removed
    report['stale_actors_replaced'] = stale

    placed, station_errors, director = place_gameplay(warnings)
    report['placed'] = placed
    report['stations_configured'] = len(STATIONS) - len(station_errors)
    report['station_property_errors'] = station_errors

    # The run is wired by the director's own auto-initialize, so report plainly
    # whether that property is exposed rather than assuming it.
    probe_name, probe_value = probe_property(director, 'bAutoInitialize')
    report['director_auto_initialize'] = {'property': probe_name, 'value': probe_value}

    play_mode = resolve_class('StarGameMode', SCRIPTS + '.StarGameMode', warnings)
    report['play_gamemode_set'] = set_map_game_mode(
        ACTORS.get_all_level_actors(), play_mode, warnings)
    report['game_mode_class'] = str(play_mode) if play_mode else None

    if not LEVEL.save_current_level():
        raise RuntimeError('could not save the playable map')
    report['saved_assets'] = u.EditorAssetLibrary.save_directory(
        ROOT, only_if_is_dirty=False, recursive=True)
    report['actor_count'] = len(ACTORS.get_all_level_actors())

    report['warnings'] = warnings
    out = Path(u.Paths.project_saved_dir()) / 'SceneReports'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'play_level_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    for warning in warnings:
        u.log_warning('STAR_PLAY_LEVEL: ' + warning)
    u.log('STAR_PLAY_LEVEL_OK ' + json.dumps(report))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Log the reason before re-raising: the commandlet log is the only place
        # an unattended run can explain itself.
        u.log_error('STAR_PLAY_LEVEL_FAILED\n' + traceback.format_exc())
        raise

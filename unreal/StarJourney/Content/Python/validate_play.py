"""Exercise actual PIE autoplay, camera binding, station lights and looping."""
import json
from pathlib import Path
import time
import traceback
import unreal as u

OUT = Path(u.Paths.project_saved_dir()) / 'SceneReports'
OUT.mkdir(parents=True, exist_ok=True)
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
EDITOR = u.get_editor_subsystem(u.UnrealEditorSubsystem)
u.EditorPythonScripting.set_keep_python_script_alive(True)
LEVEL.load_level('/Game/StarJourney/Maps/L_EchoForest')
LEVEL.editor_request_begin_play()
started = time.monotonic()
state = {'checks': [], 'samples': [], 'last_time': None, 'looped': False, 'lit': False,
         'autoplay': False, 'done': False, 'exit_after': None}


def finish(error=None):
    state['done'] = True
    state['exit_after'] = time.monotonic() + 2
    LEVEL.editor_request_end_play()
    report = {'checks': state['checks'], 'samples': state['samples'], 'error': error}
    (OUT / 'play_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    if error:
        u.log_error(error)
    else:
        u.log('STAR_SCENE_PLAY_OK')


def tick(delta):
    try:
        if state['done']:
            if time.monotonic() >= state['exit_after']:
                u.unregister_slate_post_tick_callback(handle)
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - started > 120:
            raise RuntimeError('PIE did not finish one full loop in 120 seconds')
        world = EDITOR.get_game_world()
        if not world:
            return
        directors = u.GameplayStatics.get_all_actors_of_class(world, u.LevelSequenceActor)
        if not directors or not directors[0].sequence_player:
            return
        player = directors[0].sequence_player
        if not player.is_playing():
            raise AssertionError('Sequence did not autoplay in PIE')
        qt = player.get_current_time()
        seconds = (qt.time.frame_number.value + qt.time.sub_frame) * qt.rate.denominator / qt.rate.numerator
        actors = u.GameplayStatics.get_all_actors_of_class(world, u.Actor)
        by_label = {a.get_actor_label(): a for a in actors}
        camera = by_label['CAM | Fixed rear view']
        first_light = by_label['Station 0 warm pool'].point_light_component.intensity
        if not state['autoplay'] and seconds > .3:
            controller = u.GameplayStatics.get_player_controller(world, 0)
            assert controller and controller.get_view_target() == camera, 'Game camera is not the authored camera'
            state['checks'].append('Autoplay and player camera binding passed')
            state['autoplay'] = True
        if 6.95 < seconds < 8 and not state['lit']:
            assert abs(first_light - 240) < .1, 'Station light did not reach its intended intensity'
            state['checks'].append('First station light reaches 240 after the animation')
            state['lit'] = True
        if state['last_time'] is not None and seconds < state['last_time'] - 20:
            assert state['lit'], 'Loop happened before observing the first light'
            assert first_light < 6, 'Light did not reset at loop boundary'
            assert camera.get_actor_location().x < -1200, 'Camera did not reset at loop boundary'
            state['checks'].append('30 second loop resets camera and lights')
            state['looped'] = True
            finish()
            return
        if not state['samples'] or seconds >= state['samples'][-1]['seconds'] + 5:
            state['samples'].append({'seconds': seconds, 'camera_x': camera.get_actor_location().x,
                                     'first_light_intensity': first_light})
        state['last_time'] = seconds
    except Exception:
        finish(traceback.format_exc())


handle = u.register_slate_post_tick_callback(tick)

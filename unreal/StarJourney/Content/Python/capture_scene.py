"""GPU render checks at fixed timeline positions, without saving preview state."""
import json
from pathlib import Path
import time
import traceback
import unreal as u

OUT = Path(u.Paths.project_saved_dir()) / 'SceneReports'
OUT.mkdir(parents=True, exist_ok=True)
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
ACTORS = u.get_editor_subsystem(u.EditorActorSubsystem)
SEQ = u.LevelSequenceEditorBlueprintLibrary
u.EditorPythonScripting.set_keep_python_script_alive(True)
if not LEVEL.load_level('/Game/StarJourney/Maps/L_EchoForest'):
    raise RuntimeError('Scene map missing')
sequence = u.load_asset('/Game/StarJourney/Cinematics/LS_EchoForest_30s')
SEQ.open_level_sequence(sequence)
SEQ.pause()
SEQ.set_lock_camera_cut_to_viewport(True)
LEVEL.editor_set_game_view(True)
camera = next(a for a in ACTORS.get_all_level_actors() if a.get_actor_label() == 'CAM | Fixed rear view')
shots = [('01_arrival', 0), ('02_before_light', 5.4), ('03_after_light', 6.9), ('04_deep_forest', 17), ('05_final_station', 24.9)]
state = {'index': 0, 'phase': 'seek', 'after': time.monotonic() + 10, 'task': None, 'results': []}
started = time.monotonic()


def finish(error=None):
    u.unregister_slate_post_tick_callback(handle)
    (OUT / 'capture_report.json').write_text(json.dumps({'shots': state['results'], 'error': error}, indent=2), encoding='utf-8')
    if error:
        u.log_error(error)
    else:
        u.log('STAR_SCENE_CAPTURE_OK')
    u.EditorPythonScripting.set_keep_python_script_alive(False)
    u.SystemLibrary.quit_editor()


def tick(delta):
    try:
        now = time.monotonic()
        if now - started > 420:
            finish('Screenshot pass exceeded 420 seconds')
            return
        if now < state['after']:
            return
        name, seconds = shots[state['index']]
        if state['phase'] == 'seek':
            params = u.MovieSceneSequencePlaybackParams()
            params.set_editor_property('frame', u.FrameTime(u.FrameNumber(round(seconds * 30))))
            params.set_editor_property('position_type', u.MovieScenePositionType.FRAME)
            SEQ.set_global_position(params)
            LEVEL.pilot_level_actor(camera)
            state['phase'] = 'render'
            state['after'] = now + 6
        elif state['phase'] == 'render':
            target = OUT / (name + '.png')
            if target.exists():
                target.unlink()
            state['task'] = u.AutomationLibrary.take_high_res_screenshot(1600, 900, str(OUT / (name + '.png')), camera=camera)
            state['phase'] = 'wait'
            state['after'] = now + 3
        elif state['phase'] == 'wait':
            path = OUT / (name + '.png')
            if not path.exists():
                state['after'] = now + 1
                return
            lights = [a for a in ACTORS.get_all_level_actors() if a.get_actor_label() == 'Station 0 warm pool']
            state['results'].append({'file': str(path), 'seconds': seconds, 'bytes': path.stat().st_size,
                                     'first_light_intensity': lights[0].point_light_component.intensity,
                                     'camera_x': camera.get_actor_location().x})
            state['index'] += 1
            if state['index'] >= len(shots):
                finish()
            else:
                state['phase'] = 'seek'
    except Exception:
        finish(traceback.format_exc())


handle = u.register_slate_post_tick_callback(tick)

"""Temporal rules for one front-facing player; thresholds require real-camera calibration."""
from dataclasses import dataclass
import math
import statistics
from .types import Action, Phase, TrackingState, InputEvent

@dataclass(frozen=True)
class GestureConfig:
    visibility: float = 0.6
    ready_ms: int = 600
    candidate_ms: int = 150
    return_ms: int = 250
    unready_ms: int = 450
    max_gap_ms: int = 600
    action_timeout_ms: int = 15000
    center_tolerance: float = 0.12
    leg_lift: float = 0.12
    squat_drop: float = 0.14
    jump_rise: float = 0.035
    jump_distance: float = 0.12

    def __post_init__(self):
        for name in ("ready_ms","candidate_ms","return_ms","unready_ms","max_gap_ms","action_timeout_ms"):
            if type(getattr(self,name)) is not int or getattr(self,name) <= 0:
                raise ValueError(f"gestures.{name} must be a positive integer")
        for name in ("visibility","center_tolerance","leg_lift","squat_drop","jump_rise","jump_distance"):
            value=getattr(self,name)
            if not math.isfinite(value) or not 0 < value < 1:
                raise ValueError(f"gestures.{name} must be in (0,1)")

def angle(a,b,c,aspect):
    u=((a.x-b.x)*aspect,a.y-b.y)
    v=((c.x-b.x)*aspect,c.y-b.y)
    length=math.hypot(*u)*math.hypot(*v)
    return math.degrees(math.acos(max(-1,min(1,(u[0]*v[0]+u[1]*v[1])/length)))) if length>1e-8 else 0

class GestureRecognizer:
    def __init__(self,config=None):
        self.config=config or GestureConfig()
        self.reset(0)

    def reset(self,generation):
        if type(generation) is not int or not 0 <= generation < 2**64:
            raise ValueError("generation must be uint64")
        self.generation=generation
        self.tracking_state=TrackingState.NOT_READY
        self.active_action=None
        self.reason="Stand centered, facing camera" if generation else "Waiting for UE / watch"
        self._last_ts=-1
        self._baseline=None
        self._ready_samples=[]
        self._candidate=None
        self._candidate_since=0
        self._active_since=0
        self._return_since=None
        self._unready_since=None
        self._flight_at=None

    def _state(self,state,events):
        if self.tracking_state != state:
            self.tracking_state=state
            if self.generation:
                events.append(InputEvent(self.generation,state=state))

    def _cancel(self,events):
        if self.active_action is not None:
            events.append(InputEvent(self.generation,action=self.active_action,phase=Phase.CANCEL))
            self.active_action=None
        self._candidate=None
        self._return_since=None
        self._flight_at=None

    def lost(self,generation,timestamp_ms):
        if generation != self.generation or not generation or timestamp_ms < self._last_ts:
            return []
        self._last_ts=timestamp_ms
        events=[]
        self._cancel(events)
        self._state(TrackingState.LOST,events)
        self._baseline=None
        self._ready_samples=[]
        self.reason="Tracking lost; return to center"
        return events

    def _features(self,sample):
        if len(sample.poses)!=1:
            return None
        p=sample.poses[0]
        required=(0,11,12,13,14,15,16,23,24,25,26,27,28,31,32)
        if len(p)!=33 or not math.isfinite(sample.aspect_ratio) or sample.aspect_ratio <= 0:
            return None
        for i in required:
            point=p[i]
            if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in
                       (point.x,point.y,point.visibility,point.presence)):
                return None
            if min(point.visibility,point.presence)<self.config.visibility or not (0.015<=point.x<=0.985 and 0.015<=point.y<=0.985):
                return None
        foot=(p[27].y,p[28].y)
        height=sum(foot)/2-p[0].y
        if height<0.3:
            return None
        return dict(x=(p[23].x+p[24].x)/2, hip=(p[23].y+p[24].y)/2, feet=foot,
                    height=height, knees=(angle(p[23],p[25],p[27],sample.aspect_ratio),
                                         angle(p[24],p[26],p[28],sample.aspect_ratio)),
                    arms_down=p[15].y>p[11].y+height*0.05 and p[16].y>p[12].y+height*0.05,
                    arms_up=p[15].y<p[11].y-height*0.08 and p[16].y<p[12].y-height*0.08,
                    spread=abs(p[27].x-p[28].x)*sample.aspect_ratio,
                    left_sign=1 if p[11].x>p[12].x else -1, aspect=sample.aspect_ratio)

    def _upright(self,f):
        return min(f["knees"])>155 and f["arms_down"] and abs(f["feet"][0]-f["feet"][1])<f["height"]*0.07

    def _neutral(self,f):
        if not self._upright(f):
            return False
        b=self._baseline
        if b is None:
            return 0.35 <= f["x"] <= 0.65
        h=b["height"]
        return (abs((f["x"]-b["x"])*f["aspect"]) < h*self.config.center_tolerance and
                abs(f["hip"]-b["hip"]) < h*0.08 and
                all(abs(a-v)<h*0.07 for a,v in zip(f["feet"],b["feet"])) and
                f["spread"]<max(b["spread"]*1.35,h*0.3))

    def _prepare(self,f,t,events):
        if not self._neutral(f):
            self._ready_samples=[]
            self.reason="Return to center; stand upright with feet together and arms down"
            self._state(TrackingState.NOT_READY,events)
            return
        if self._ready_samples:
            previous=self._ready_samples[-1][1]
            if abs(f["x"]-previous["x"])>f["height"]*0.025 or abs(f["hip"]-previous["hip"])>f["height"]*0.025:
                self._ready_samples=[]
        self._ready_samples.append((t,f))
        self._ready_samples=self._ready_samples[-120:]
        self._state(TrackingState.NOT_READY,events)
        if t-self._ready_samples[0][0]>=self.config.ready_ms:
            if self._baseline is None:
                samples=[v for _,v in self._ready_samples]
                self._baseline=dict(f)
                for key in ("x","hip","height","spread"):
                    self._baseline[key]=statistics.median(s[key] for s in samples)
                self._baseline["feet"]=tuple(statistics.median(s["feet"][i] for s in samples) for i in (0,1))
            self._ready_samples=[]
            self._state(TrackingState.READY,events)
            self.reason="Ready"

    def _classify(self,f,t):
        b=self._baseline
        h=b["height"]
        displacement=(f["x"]-b["x"])*f["aspect"]/h
        lifts=tuple((base-now)/h for base,now in zip(b["feet"],f["feet"]))
        rise=(b["hip"]-f["hip"])/h
        if min(lifts)>self.config.jump_rise and rise>self.config.jump_rise:
            self._flight_at=t
        # Joint condition first: never reinterpret a jack as a permitted leg raise.
        if f["arms_up"] and f["spread"]>max(b["spread"]*1.7,h*0.42):
            return Action.JUMPING_JACK
        if f["arms_down"] and self._flight_at is not None and t-self._flight_at<=300 and abs(displacement)>self.config.jump_distance:
            return Action.JUMP_LEFT if displacement*b["left_sign"]>0 else Action.JUMP_RIGHT
        if f["arms_down"] and abs(displacement)<self.config.center_tolerance:
            if (f["hip"]-b["hip"])/h>self.config.squat_drop and max(f["knees"])<145:
                return Action.SQUAT
            for side,action in ((0,Action.LEFT_LEG),(1,Action.RIGHT_LEG)):
                if lifts[side]>self.config.leg_lift and abs(lifts[1-side])<0.06 and rise<self.config.jump_rise:
                    return action
        return None

    def observe(self,sample):
        if not sample.generation or sample.generation!=self.generation or sample.timestamp_ms<=self._last_ts:
            return []
        t=sample.timestamp_ms
        if self._last_ts>=0 and t-self._last_ts>self.config.max_gap_ms:
            return self.lost(sample.generation,t)
        f=self._features(sample)
        if f is None:
            events=self.lost(sample.generation,t)
            self.reason="Multiple people: clear the play area" if len(sample.poses)>1 else "Keep one full body visible"
            return events
        self._last_ts=t
        events=[]
        if self.active_action is not None:
            if t-self._active_since>self.config.action_timeout_ms:
                self._cancel(events)
                self._state(TrackingState.NOT_READY,events)
                self._ready_samples=[]
                self.reason="Action timed out; stand centered again"
                return events
            if self._neutral(f):
                if self._return_since is None:
                    self._return_since=t
                if t-self._return_since>=self.config.return_ms:
                    events.append(InputEvent(self.generation,action=self.active_action,phase=Phase.COMPLETE))
                    self.active_action=None
                    self._return_since=None
                    self._flight_at=None
                    self._state(TrackingState.READY,events)
                    self.reason="Ready"
            else:
                self._return_since=None
                self.reason="Finish action, then return to center"
            return events
        if self.tracking_state != TrackingState.READY:
            self._prepare(f,t,events)
            return events
        candidate=self._classify(f,t)
        if candidate is not None:
            self._unready_since=None
            if candidate != self._candidate:
                self._candidate=candidate
                self._candidate_since=t
            if t-self._candidate_since>=self.config.candidate_ms:
                self.active_action=candidate
                self._active_since=t
                self._candidate=None
                # Internal readiness changes with Begin; do not emit NotReady before Begin.
                self.tracking_state=TrackingState.NOT_READY
                self.reason="Finish action, then return to center"
                events.append(InputEvent(self.generation,action=candidate,phase=Phase.BEGIN))
        else:
            self._candidate=None
            if self._neutral(f):
                self._unready_since=None
                self.reason="Ready"
            else:
                if self._unready_since is None:
                    self._unready_since=t
                if t-self._unready_since>=self.config.unready_ms:
                    self._state(TrackingState.NOT_READY,events)
                    self._ready_samples=[]
                    self.reason="Unrecognized motion; return to center"
        return events

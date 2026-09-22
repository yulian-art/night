package input

import (
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	pb "night/gen/star/v1"
	"testing"
)

func action(g uint64, a pb.Action, p pb.Phase) *pb.InputEvent {
	return &pb.InputEvent{Event: &pb.InputEvent_Action{Action: &pb.ActionEvent{Generation: g, Action: a, Phase: p}}}
}
func TestCycleAndGeneration(t *testing.T) {
	h := New(16)
	producer, _ := h.Attach()
	sub, _ := h.Subscribe(1)
	<-sub.Events
	ready := tracking(1, pb.TrackingState_TRACKING_STATE_READY)
	begin := action(1, pb.Action_ACTION_SQUAT, pb.Phase_PHASE_BEGIN)
	complete := action(1, pb.Action_ACTION_SQUAT, pb.Phase_PHASE_COMPLETE)
	if err := h.Publish(producer, begin); status.Code(err) != codes.FailedPrecondition {
		t.Fatalf("Begin without Ready: %v", err)
	}
	for _, e := range []*pb.InputEvent{ready, begin, complete} {
		if err := h.Publish(producer, e); err != nil {
			t.Fatal(err)
		}
	}
	if err := h.Publish(producer, complete); status.Code(err) != codes.FailedPrecondition {
		t.Fatalf("duplicate complete: %v", err)
	}
	if err := h.Publish(producer, begin); status.Code(err) != codes.FailedPrecondition {
		t.Fatalf("must re-ready: %v", err)
	}
	newer, err := h.Subscribe(2)
	if err != nil {
		t.Fatal(err)
	}
	<-newer.Events
	if status.Code(sub.Err()) != codes.Aborted {
		t.Fatal("old stream not aborted")
	}
	if err := h.Publish(producer, ready); err != nil {
		t.Fatal(err)
	}
	if err := h.Publish(producer, action(2, pb.Action_ACTION_SQUAT, pb.Phase_PHASE_BEGIN)); status.Code(err) != codes.FailedPrecondition {
		t.Fatal("old ready affected new generation")
	}
	if len(newer.Events) != 0 {
		t.Fatal("replayed stale input")
	}
	if _, err := h.Subscribe(2); status.Code(err) != codes.FailedPrecondition {
		t.Fatal("reused generation")
	}
	h.Unsubscribe(sub)
	if h.sub != newer {
		t.Fatal("old cleanup closed new stream")
	}
}
func TestLostCancelsAndOverflowFails(t *testing.T) {
	h := New(8)
	p, _ := h.Attach()
	s, _ := h.Subscribe(1)
	<-s.Events
	for _, e := range []*pb.InputEvent{tracking(1, pb.TrackingState_TRACKING_STATE_READY), action(1, pb.Action_ACTION_SQUAT, pb.Phase_PHASE_BEGIN), tracking(1, pb.TrackingState_TRACKING_STATE_LOST)} {
		if err := h.Publish(p, e); err != nil {
			t.Fatal(err)
		}
	}
	<-s.Events
	<-s.Events
	if got := (<-s.Events).GetAction(); got.GetPhase() != pb.Phase_PHASE_CANCEL {
		t.Fatal("Lost must cancel squat")
	}
	if got := (<-s.Events).GetTracking(); got.GetState() != pb.TrackingState_TRACKING_STATE_LOST {
		t.Fatal("Lost order")
	}
	if err := h.Publish(p, action(1, pb.Action_ACTION_SQUAT, pb.Phase_PHASE_COMPLETE)); status.Code(err) != codes.FailedPrecondition {
		t.Fatal("cancel was consumed as complete")
	}
	h = New(1)
	p, _ = h.Attach()
	s, _ = h.Subscribe(1)
	if err := h.Publish(p, tracking(1, pb.TrackingState_TRACKING_STATE_READY)); status.Code(err) != codes.ResourceExhausted {
		t.Fatalf("overflow: %v", err)
	}
	if status.Code(s.Err()) != codes.ResourceExhausted {
		t.Fatal("overflow not signaled to UE")
	}
}
func TestProducerDisconnectAndExclusivity(t *testing.T) {
	h := New(8)
	p, _ := h.Attach()
	s, _ := h.Subscribe(1)
	if _, err := h.Attach(); status.Code(err) != codes.AlreadyExists {
		t.Fatal("multiple producers")
	}
	h.Detach(p)
	if status.Code(s.Err()) != codes.Unavailable {
		t.Fatal("recognizer loss not reported")
	}
	next, _ := h.Attach()
	if got := <-next.Resets; got != 0 {
		t.Fatal("reconnected producer inherited old input")
	}
}

func TestAllActionsRequireMatchingEndAndFreshReady(t *testing.T) {
	for a := pb.Action_ACTION_SQUAT; a <= pb.Action_ACTION_JUMPING_JACK; a++ {
		t.Run(a.String(), func(t *testing.T) {
			h := New(16)
			p, _ := h.Attach()
			s, _ := h.Subscribe(1)
			<-s.Events
			for _, e := range []*pb.InputEvent{tracking(1, pb.TrackingState_TRACKING_STATE_READY), action(1, a, pb.Phase_PHASE_BEGIN)} {
				if err := h.Publish(p, e); err != nil {
					t.Fatal(err)
				}
			}
			wrong := pb.Action(1 + int32(a)%6)
			for _, e := range []*pb.InputEvent{action(1, wrong, pb.Phase_PHASE_COMPLETE), tracking(1, pb.TrackingState_TRACKING_STATE_READY), tracking(1, pb.TrackingState_TRACKING_STATE_NOT_READY), action(1, wrong, pb.Phase_PHASE_BEGIN)} {
				if err := h.Publish(p, e); status.Code(err) != codes.FailedPrecondition {
					t.Fatalf("accepted invalid transition %v: %v", e, err)
				}
			}
			if err := h.Publish(p, action(1, a, pb.Phase_PHASE_CANCEL)); err != nil {
				t.Fatal(err)
			}
			if err := h.Publish(p, action(1, a, pb.Phase_PHASE_BEGIN)); status.Code(err) != codes.FailedPrecondition {
				t.Fatal("Cancel incorrectly restored Ready")
			}
		})
	}
}

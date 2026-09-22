// Package input bridges one recognizer and one UE stream. It never replays input.
package input

import (
	"sync"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
	pb "night/gen/star/v1"
)

type Subscription struct {
	Events     chan *pb.InputEvent
	Done       chan struct{}
	err        error // written before Done closes
	generation uint64
}

func (s *Subscription) Err() error { <-s.Done; return s.err }

type Producer struct{ Resets chan uint64 }

type Hub struct {
	mu         sync.Mutex
	capacity   int
	generation uint64
	sub        *Subscription
	producer   *Producer
	ready      bool
	active     pb.Action
}

func New(capacity int) *Hub {
	if capacity < 1 {
		panic("input queue capacity must be positive")
	}
	return &Hub{capacity: capacity}
}
func tracking(g uint64, state pb.TrackingState) *pb.InputEvent {
	return &pb.InputEvent{Event: &pb.InputEvent_Tracking{Tracking: &pb.TrackingEvent{Generation: g, State: state}}}
}
func (h *Hub) resetLocked(g uint64) {
	h.ready = false
	h.active = pb.Action_ACTION_UNSPECIFIED
	if h.producer != nil {
		// Only the latest reset matters. In-flight old frames retain their old ID.
		select {
		case <-h.producer.Resets:
		default:
		}
		h.producer.Resets <- g
	}
}
func (h *Hub) stopLocked(err error) {
	if h.sub != nil {
		h.sub.err = err
		close(h.sub.Done)
		h.sub = nil
	}
	h.resetLocked(0)
}
func (h *Hub) Subscribe(g uint64) (*Subscription, error) {
	h.mu.Lock()
	defer h.mu.Unlock()
	if g == 0 || g <= h.generation {
		return nil, status.Errorf(codes.FailedPrecondition, "generation must exceed %d", h.generation)
	}
	if h.sub != nil {
		h.sub.err = status.Error(codes.Aborted, "input generation replaced")
		close(h.sub.Done)
	}
	h.generation = g
	s := &Subscription{Events: make(chan *pb.InputEvent, h.capacity), Done: make(chan struct{}), generation: g}
	h.sub = s
	s.Events <- tracking(g, pb.TrackingState_TRACKING_STATE_NOT_READY)
	h.resetLocked(g)
	return s, nil
}
func (h *Hub) Unsubscribe(s *Subscription) {
	h.mu.Lock()
	defer h.mu.Unlock()
	if h.sub == s {
		h.stopLocked(status.Error(codes.Canceled, "UE disconnected"))
	}
}
func (h *Hub) Attach() (*Producer, error) {
	h.mu.Lock()
	defer h.mu.Unlock()
	if h.producer != nil {
		return nil, status.Error(codes.AlreadyExists, "recognizer already connected")
	}
	p := &Producer{Resets: make(chan uint64, 1)}
	h.producer = p
	g := uint64(0)
	if h.sub != nil {
		g = h.sub.generation
	}
	h.resetLocked(g)
	return p, nil
}
func (h *Hub) Detach(p *Producer) {
	h.mu.Lock()
	defer h.mu.Unlock()
	if h.producer == p {
		h.producer = nil
		h.stopLocked(status.Error(codes.Unavailable, "recognizer disconnected; pause and open a new generation"))
	}
}
func (h *Hub) enqueueLocked(e *pb.InputEvent) error {
	select {
	case h.sub.Events <- e:
		return nil
	default:
		err := status.Error(codes.ResourceExhausted, "input queue overflow; pause and open a new generation")
		h.stopLocked(err)
		return err
	}
}
func (h *Hub) Publish(p *Producer, e *pb.InputEvent) error {
	h.mu.Lock()
	defer h.mu.Unlock()
	if p != h.producer {
		return status.Error(codes.FailedPrecondition, "inactive recognizer")
	}
	var g uint64
	switch event := e.GetEvent().(type) {
	case *pb.InputEvent_Action:
		g = event.Action.GetGeneration()
	case *pb.InputEvent_Tracking:
		g = event.Tracking.GetGeneration()
	default:
		return status.Error(codes.InvalidArgument, "input event is required")
	}
	// Stale inference results never touch the new cycle, including malformed ones.
	if h.sub == nil || g != h.sub.generation {
		return nil
	}
	if a := e.GetAction(); a != nil {
		if a.Action < pb.Action_ACTION_SQUAT || a.Action > pb.Action_ACTION_JUMPING_JACK {
			return status.Error(codes.InvalidArgument, "unknown action")
		}
		switch a.Phase {
		case pb.Phase_PHASE_BEGIN:
			if !h.ready || h.active != pb.Action_ACTION_UNSPECIFIED {
				return status.Error(codes.FailedPrecondition, "Begin requires Ready and no active action")
			}
			h.ready = false
			h.active = a.Action
		case pb.Phase_PHASE_COMPLETE, pb.Phase_PHASE_CANCEL:
			if h.active != a.Action {
				return status.Error(codes.FailedPrecondition, "Complete/Cancel must match the active action")
			}
			h.active = pb.Action_ACTION_UNSPECIFIED
		default:
			return status.Error(codes.InvalidArgument, "unknown phase")
		}
	} else if t := e.GetTracking(); t != nil {
		switch t.State {
		case pb.TrackingState_TRACKING_STATE_LOST:
			if h.active != pb.Action_ACTION_UNSPECIFIED {
				cancel := &pb.InputEvent{Event: &pb.InputEvent_Action{Action: &pb.ActionEvent{Generation: g, Action: h.active, Phase: pb.Phase_PHASE_CANCEL}}}
				if err := h.enqueueLocked(cancel); err != nil {
					return err
				}
			}
			h.active = pb.Action_ACTION_UNSPECIFIED
			h.ready = false
		case pb.TrackingState_TRACKING_STATE_READY, pb.TrackingState_TRACKING_STATE_NOT_READY:
			if h.active != pb.Action_ACTION_UNSPECIFIED {
				return status.Error(codes.FailedPrecondition, "finish or cancel the active action before changing readiness")
			}
			h.ready = t.State == pb.TrackingState_TRACKING_STATE_READY
		default:
			return status.Error(codes.InvalidArgument, "unknown tracking state")
		}
	}
	return h.enqueueLocked(proto.Clone(e).(*pb.InputEvent))
}

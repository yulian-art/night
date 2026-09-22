package service

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"time"

	"github.com/gorilla/websocket"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	pb "night/gen/star/v1"
	"night/internal/input"
)

// WS gateway: serve UE over plain WebSocket+JSON so the engine needs no gRPC
// plugin. Semantics mirror WatchInput exactly; only the transport differs.
//
// Connect:  ws://127.0.0.1:<port>/ws/input?generation=<uint64>
// Server pushes one JSON message per InputEvent, in order, until the stream
// ends (generation replaced, queue overflow, recognizer or UE disconnect).

const (
	// wsSendBuffer bounds how many events queue for a slow UE before we close.
	// Matches the gRPC default queue capacity philosophy: never drop Complete.
	wsSendBuffer  = 64
	wsWriteWait   = 5 * time.Second
	wsPongWait    = 60 * time.Second
	wsPingPeriod  = 30 * time.Second
	wsMaxMsgBytes = 4096
)

// wsEvent is the JSON wire form of one InputEvent. Exactly one of
// tracking/action is present; generation is a decimal string because UE JSON
// and JavaScript-style numbers cannot hold a full uint64.
type wsEvent struct {
	Tracking *wsTracking `json:"tracking,omitempty"`
	Action   *wsAction   `json:"action,omitempty"`
}

type wsTracking struct {
	Generation string `json:"generation"`
	State      string `json:"state"` // LOST | NOT_READY | READY
}

type wsAction struct {
	Generation string `json:"generation"`
	Action     string `json:"action"` // SQUAT | LEFT_LEG | ... | JUMPING_JACK
	Phase      string `json:"phase"`  // BEGIN | COMPLETE | CANCEL
}

// wsError is sent as the final message before the server closes the socket on
// a stream error, so UE can distinguish "pause and re-ready" from a clean end.
type wsError struct {
	Error string `json:"error"`
	Code  string `json:"code"`
}

var wsUpgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 4096,
	// Loopback-only service; the listener already enforces the IP. Same-origin
	// policy does not apply to a game client, so accept the upgrade.
	CheckOrigin: func(r *http.Request) bool { return true },
}

// actionName maps proto enum values to the short names UE switches on.
func actionName(a pb.Action) string {
	switch a {
	case pb.Action_ACTION_SQUAT:
		return "SQUAT"
	case pb.Action_ACTION_LEFT_LEG:
		return "LEFT_LEG"
	case pb.Action_ACTION_RIGHT_LEG:
		return "RIGHT_LEG"
	case pb.Action_ACTION_JUMP_LEFT:
		return "JUMP_LEFT"
	case pb.Action_ACTION_JUMP_RIGHT:
		return "JUMP_RIGHT"
	case pb.Action_ACTION_JUMPING_JACK:
		return "JUMPING_JACK"
	default:
		return "UNSPECIFIED"
	}
}

func phaseName(p pb.Phase) string {
	switch p {
	case pb.Phase_PHASE_BEGIN:
		return "BEGIN"
	case pb.Phase_PHASE_COMPLETE:
		return "COMPLETE"
	case pb.Phase_PHASE_CANCEL:
		return "CANCEL"
	default:
		return "UNSPECIFIED"
	}
}

func trackingName(s pb.TrackingState) string {
	switch s {
	case pb.TrackingState_TRACKING_STATE_LOST:
		return "LOST"
	case pb.TrackingState_TRACKING_STATE_NOT_READY:
		return "NOT_READY"
	case pb.TrackingState_TRACKING_STATE_READY:
		return "READY"
	default:
		return "UNSPECIFIED"
	}
}

// toWSEvent converts one InputEvent to its JSON form. Returns nil for an
// empty/unknown event, which the caller skips.
func toWSEvent(e *pb.InputEvent) *wsEvent {
	if t := e.GetTracking(); t != nil {
		return &wsEvent{Tracking: &wsTracking{
			Generation: strconv.FormatUint(t.GetGeneration(), 10),
			State:      trackingName(t.GetState()),
		}}
	}
	if a := e.GetAction(); a != nil {
		return &wsEvent{Action: &wsAction{
			Generation: strconv.FormatUint(a.GetGeneration(), 10),
			Action:     actionName(a.GetAction()),
			Phase:      phaseName(a.GetPhase()),
		}}
	}
	return nil
}

// WSGateway bridges the input Hub to WebSocket clients. It owns no game state;
// all generation/ordering/overflow rules stay in the Hub.
type WSGateway struct {
	hub *input.Hub
}

func NewWSGateway(hub *input.Hub) *WSGateway { return &WSGateway{hub: hub} }

// ServeHTTP handles GET /ws/input?generation=<uint64>.
func (g *WSGateway) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	generation, err := parseGeneration(r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	conn, err := wsUpgrader.Upgrade(w, r, nil)
	if err != nil {
		// Upgrade already wrote the error response.
		return
	}
	defer conn.Close()

	sub, err := g.hub.Subscribe(generation)
	if err != nil {
		writeWSClose(conn, err)
		return
	}
	defer g.hub.Unsubscribe(sub)

	// Forward Hub events to the socket; stop when the Hub closes the
	// subscription or the write pump reports a dead client.
	if err := g.pump(conn, sub); err != nil {
		writeWSClose(conn, err)
	}
}

// parseGeneration reads and validates the ?generation query parameter.
func parseGeneration(r *http.Request) (uint64, error) {
	raw := r.URL.Query().Get("generation")
	if raw == "" {
		return 0, errors.New("missing required query parameter: generation")
	}
	generation, err := strconv.ParseUint(raw, 10, 64)
	if err != nil || generation == 0 {
		return 0, errors.New("generation must be a positive uint64")
	}
	return generation, nil
}

// pump streams subscription events to conn until the Hub ends the
// subscription, the context is cancelled, or a write fails. A read pump runs
// alongside only to detect client disconnect and answer pings; UE sends no
// messages on this socket.
func (g *WSGateway) pump(conn *websocket.Conn, sub *input.Subscription) error {
	conn.SetReadLimit(wsMaxMsgBytes)
	_ = conn.SetReadDeadline(time.Now().Add(wsPongWait))
	conn.SetPongHandler(func(string) error {
		return conn.SetReadDeadline(time.Now().Add(wsPongWait))
	})

	// readPump only observes closure; its result selects which error wins.
	closed := make(chan error, 1)
	go func() {
		for {
			if _, _, err := conn.ReadMessage(); err != nil {
				closed <- err
				return
			}
		}
	}()

	ping := time.NewTicker(wsPingPeriod)
	defer ping.Stop()
	// On return, unblock readPump so its goroutine exits instead of leaking
	// until ServeHTTP's deferred conn.Close runs.
	defer func() { _ = conn.Close() }()

	for {
		select {
		case err := <-closed:
			// Client went away (or read error); nothing more to send.
			return readCloseError(err)
		case <-sub.Done:
			return sub.Err()
		case event := <-sub.Events:
			payload := toWSEvent(event)
			if payload == nil {
				continue
			}
			data, err := json.Marshal(payload)
			if err != nil {
				return err
			}
			if err := writeWSMessage(conn, data); err != nil {
				return err
			}
		case <-ping.C:
			if err := writeWSControl(conn, websocket.PingMessage, nil); err != nil {
				return err
			}
		}
	}
}

// writeWSMessage sends one JSON text frame with a write deadline.
func writeWSMessage(conn *websocket.Conn, data []byte) error {
	_ = conn.SetWriteDeadline(time.Now().Add(wsWriteWait))
	return conn.WriteMessage(websocket.TextMessage, data)
}

// writeWSControl sends a ping/pong/close control frame with a write deadline.
func writeWSControl(conn *websocket.Conn, msgType int, data []byte) error {
	_ = conn.SetWriteDeadline(time.Now().Add(wsWriteWait))
	return conn.WriteMessage(msgType, data)
}

// writeWSClose best-effort sends a terminal JSON error then a WebSocket close
// frame so UE sees the reason before the socket closes.
func writeWSClose(conn *websocket.Conn, err error) {
	code, message := describeStreamError(err)
	if payload, mErr := json.Marshal(wsError{Error: message, Code: code}); mErr == nil {
		_ = writeWSMessage(conn, payload)
	}
	// 1011 = internal error, 1000 = normal; UE only needs a clean close.
	closeCode := websocket.CloseNormalClosure
	if code != "canceled" {
		closeCode = websocket.CloseInternalServerErr
	}
	_ = writeWSControl(conn, websocket.CloseMessage,
		websocket.FormatCloseMessage(closeCode, message))
}

// describeStreamError maps a Hub/gRPC status error to a stable code string UE
// can branch on, plus a human-readable message.
func describeStreamError(err error) (code, message string) {
	if err == nil {
		return "ok", "stream ended"
	}
	switch status.Code(err) {
	case codes.Aborted:
		return "aborted", "input generation replaced; open a new generation"
	case codes.Canceled:
		return "canceled", "stream canceled"
	case codes.Unavailable:
		return "unavailable", "recognizer disconnected; pause and open a new generation"
	case codes.ResourceExhausted:
		return "resource_exhausted", "input queue overflow; pause and open a new generation"
	case codes.FailedPrecondition:
		return "failed_precondition", err.Error()
	default:
		return "internal", "stream error"
	}
}

// readCloseError converts a WebSocket read error into a benign nil for an
// expected client close, or the error otherwise.
func readCloseError(err error) error {
	if err == nil {
		return nil
	}
	var closeErr *websocket.CloseError
	if errors.As(err, &closeErr) {
		switch closeErr.Code {
		case websocket.CloseNormalClosure, websocket.CloseGoingAway, websocket.CloseNoStatusReceived:
			return nil
		}
	}
	return err
}

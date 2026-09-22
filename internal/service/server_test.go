package service

import (
	"context"
	"net"
	"path/filepath"
	"testing"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	"google.golang.org/grpc/test/bufconn"
	"google.golang.org/protobuf/proto"
	pb "night/gen/star/v1"
	"night/internal/input"
	"night/internal/storage"
)

func TestGRPCBridgeAndStorage(t *testing.T) {
	store, err := storage.Open(filepath.Join(t.TempDir(), "star.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	listener := bufconn.Listen(1024 * 1024)
	defer listener.Close()
	server := grpc.NewServer()
	defer server.Stop()
	impl := New(input.New(64), store)
	pb.RegisterStarServiceServer(server, impl)
	pb.RegisterRecognizerServiceServer(server, impl)
	go func() { _ = server.Serve(listener) }()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	conn, err := grpc.NewClient("passthrough:///test", grpc.WithTransportCredentials(insecure.NewCredentials()), grpc.WithContextDialer(func(context.Context, string) (net.Conn, error) { return listener.Dial() }))
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	client := pb.NewStarServiceClient(conn)
	recognition, err := pb.NewRecognizerServiceClient(conn).Connect(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if reset, err := recognition.Recv(); err != nil || reset.GetGeneration() != 0 {
		t.Fatalf("initial reset: %v %v", reset, err)
	}
	stream, err := client.WatchInput(ctx, &pb.WatchInputRequest{Generation: 1})
	if err != nil {
		t.Fatal(err)
	}
	if e, err := stream.Recv(); err != nil || e.GetTracking().GetState() != pb.TrackingState_TRACKING_STATE_NOT_READY {
		t.Fatalf("initial state: %v %v", e, err)
	}
	if reset, err := recognition.Recv(); err != nil || reset.GetGeneration() != 1 {
		t.Fatalf("reset: %v %v", reset, err)
	}
	events := []*pb.InputEvent{
		{Event: &pb.InputEvent_Tracking{Tracking: &pb.TrackingEvent{Generation: 1, State: pb.TrackingState_TRACKING_STATE_READY}}},
		{Event: &pb.InputEvent_Action{Action: &pb.ActionEvent{Generation: 1, Action: pb.Action_ACTION_JUMP_LEFT, Phase: pb.Phase_PHASE_BEGIN}}},
		{Event: &pb.InputEvent_Action{Action: &pb.ActionEvent{Generation: 1, Action: pb.Action_ACTION_JUMP_LEFT, Phase: pb.Phase_PHASE_COMPLETE}}},
	}
	for _, e := range events {
		if err := recognition.Send(e); err != nil {
			t.Fatal(err)
		}
		got, err := stream.Recv()
		if err != nil || !proto.Equal(got, e) {
			t.Fatalf("ordered bridge: %v %v", got, err)
		}
	}
	if err := recognition.CloseSend(); err != nil {
		t.Fatal(err)
	}
	if _, err := stream.Recv(); status.Code(err) != codes.Unavailable {
		t.Fatalf("disconnect: %v", err)
	}
	run := &pb.Run{RunId: "grpc-run", LevelId: 1, Score: 12}
	saved, err := client.SaveRun(ctx, &pb.SaveRunRequest{Run: run})
	if err != nil || !proto.Equal(saved.GetRun(), run) {
		t.Fatalf("save: %v %v", saved, err)
	}
	if _, err := client.SaveRun(ctx, &pb.SaveRunRequest{}); status.Code(err) != codes.InvalidArgument {
		t.Fatalf("validation: %v", err)
	}
	progress, err := client.GetProgress(ctx, &pb.GetProgressRequest{})
	if err != nil || !progress.Levels[1].Unlocked {
		t.Fatalf("progress: %v %v", progress, err)
	}
}

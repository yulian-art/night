package savequeue

import (
	"context"
	"errors"
	pb "night/gen/star/v1"
	"os"
	"path/filepath"
	"testing"
)

func TestFailureAndRestartRetainAllUnacknowledgedRuns(t *testing.T) {
	path := filepath.Join(t.TempDir(), "pending.json")
	q, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	for _, id := range []string{"one", "two", "one"} {
		if err := q.Enqueue(&pb.Run{RunId: id, LevelId: 1}); err != nil {
			t.Fatal(err)
		}
	}
	if q.Len() != 2 {
		t.Fatal("enqueue overwrote or duplicated runs")
	}
	outage := errors.New("network unavailable")
	err = q.Flush(context.Background(), func(_ context.Context, req *pb.SaveRunRequest) (*pb.SaveRunResponse, error) {
		if req.Run.RunId == "two" {
			return nil, outage
		}
		return &pb.SaveRunResponse{Run: req.Run}, nil
	})
	if !errors.Is(err, outage) {
		t.Fatal(err)
	}
	q, err = Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if q.Len() != 1 {
		t.Fatal("unacknowledged run lost")
	}
	if err = q.Flush(context.Background(), func(_ context.Context, req *pb.SaveRunRequest) (*pb.SaveRunResponse, error) {
		if req.Run.RunId != "two" {
			t.Fatal("wrong pending run")
		}
		return &pb.SaveRunResponse{Run: req.Run}, nil
	}); err != nil {
		t.Fatal(err)
	}
	q, err = Open(path)
	if err != nil || q.Len() != 0 {
		t.Fatalf("acknowledged run retained: %v", err)
	}
}
func TestCorruptionAndWrongAcknowledgement(t *testing.T) {
	path := filepath.Join(t.TempDir(), "pending.json")
	if err := os.WriteFile(path, []byte("broken"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(path); err == nil {
		t.Fatal("corruption silently discarded")
	}
	q, _ := Open(filepath.Join(t.TempDir(), "pending.json"))
	if err := q.Enqueue(&pb.Run{RunId: "one"}); err != nil {
		t.Fatal(err)
	}
	if err := q.Flush(context.Background(), func(context.Context, *pb.SaveRunRequest) (*pb.SaveRunResponse, error) {
		return &pb.SaveRunResponse{Run: &pb.Run{RunId: "wrong"}}, nil
	}); err == nil || q.Len() != 1 {
		t.Fatal("wrong acknowledgement removed run")
	}
}

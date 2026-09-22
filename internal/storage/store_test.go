package storage

import (
	"context"
	"google.golang.org/protobuf/proto"
	pb "night/gen/star/v1"
	"path/filepath"
	"sync"
	"testing"
)

func TestSaveRetryProgressAndReopen(t *testing.T) {
	path := filepath.Join(t.TempDir(), "star.db")
	s, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()
	initial, _ := s.Progress(ctx)
	if !initial.Levels[0].Unlocked || initial.Levels[1].Unlocked || initial.Levels[2].Unlocked {
		t.Fatal(initial)
	}
	run := &pb.Run{RunId: "one", LevelId: 1, Score: 100, ActiveMs: 2000, ActionCounts: map[int32]int64{1: 2, 6: 1}}
	if _, err := s.Save(ctx, run); err != nil {
		t.Fatal(err)
	}
	retry, err := s.Save(ctx, &pb.Run{RunId: "one", LevelId: 3, Score: 999})
	if err != nil || !proto.Equal(retry, run) {
		t.Fatalf("retry changed original: %v %v", retry, err)
	}
	if _, err := s.Save(ctx, &pb.Run{RunId: "two", LevelId: 1, Score: 5}); err != nil {
		t.Fatal(err)
	}
	if err := s.Close(); err != nil {
		t.Fatal(err)
	}
	s, err = Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	progress, err := s.Progress(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if !progress.Levels[0].Completed || progress.Levels[0].BestScore != 100 || !progress.Levels[1].Unlocked || progress.Levels[2].Unlocked || progress.Levels[2].Completed {
		t.Fatal(progress)
	}
}
func TestRollbackAndConcurrentRetry(t *testing.T) {
	s, err := Open(filepath.Join(t.TempDir(), "star.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	ctx := context.Background()
	run := &pb.Run{RunId: "same", LevelId: 1, Score: 10}
	// Force the second write to fail: the first write must roll back.
	_, err = s.db.Exec(`CREATE TRIGGER fail_progress BEFORE INSERT ON progress BEGIN SELECT RAISE(ABORT,'test failure'); END`)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = s.Save(ctx, run); err == nil {
		t.Fatal("expected failed transaction")
	}
	var count int
	if err = s.db.QueryRow(`SELECT count(*) FROM runs`).Scan(&count); err != nil || count != 0 {
		t.Fatalf("partial transaction: %d %v", count, err)
	}
	if _, err = s.db.Exec(`DROP TRIGGER fail_progress`); err != nil {
		t.Fatal(err)
	}
	var wg sync.WaitGroup
	for i := 0; i < 12; i++ {
		wg.Go(func() {
			if _, err := s.Save(ctx, run); err != nil {
				t.Error(err)
			}
		})
	}
	wg.Wait()
	if err = s.db.QueryRow(`SELECT count(*) FROM runs`).Scan(&count); err != nil || count != 1 {
		t.Fatalf("duplicates: %d %v", count, err)
	}
	for _, r := range []*pb.Run{nil, {RunId: "bad", LevelId: 4}, {RunId: "bad", LevelId: 1, Score: -1}, {RunId: "bad", LevelId: 1, ActionCounts: map[int32]int64{0: 1}}} {
		if _, err := s.Save(ctx, r); err != ErrInvalidRun {
			t.Fatalf("invalid input: %v", err)
		}
	}
}

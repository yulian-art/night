// Package savequeue is a single-process durable outbox for completed game runs.
// Enqueue before attempting SaveRun; Flush removes only acknowledged records.
package savequeue

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sync"

	"google.golang.org/protobuf/proto"
	pb "night/gen/star/v1"
)

type Queue struct {
	mu   sync.Mutex
	path string
	runs []*pb.Run
}

// Open requires exclusive process ownership of path. Corrupt files are reported,
// never replaced with an empty queue. This queue does not manage AutoDemo runs.
func Open(path string) (*Queue, error) {
	q := &Queue{path: path}
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return q, nil
	}
	if err != nil {
		return nil, err
	}
	if err = json.Unmarshal(data, &q.runs); err != nil {
		return nil, fmt.Errorf("read pending runs: %w", err)
	}
	seen := make(map[string]bool)
	for _, run := range q.runs {
		if run == nil || run.RunId == "" || seen[run.RunId] {
			return nil, fmt.Errorf("invalid pending run list")
		}
		seen[run.RunId] = true
	}
	return q, nil
}
func (q *Queue) Enqueue(run *pb.Run) error {
	q.mu.Lock()
	defer q.mu.Unlock()
	if run == nil || run.RunId == "" {
		return fmt.Errorf("run_id is required")
	}
	for _, pending := range q.runs {
		if pending.RunId == run.RunId {
			return nil
		}
	}
	next := append(append([]*pb.Run(nil), q.runs...), proto.Clone(run).(*pb.Run))
	if err := q.write(next); err != nil {
		return err
	}
	q.runs = next
	return nil
}

// Flush stops on the first failure. The caller supplies an RPC with a deadline.
// If the server commits but its reply is lost, the retained run_id safely retries.
func (q *Queue) Flush(ctx context.Context, save func(context.Context, *pb.SaveRunRequest) (*pb.SaveRunResponse, error)) error {
	q.mu.Lock()
	defer q.mu.Unlock()
	for len(q.runs) > 0 {
		if err := ctx.Err(); err != nil {
			return err
		}
		run := q.runs[0]
		response, err := save(ctx, &pb.SaveRunRequest{Run: proto.Clone(run).(*pb.Run)})
		if err != nil {
			return err
		}
		if response.GetRun().GetRunId() != run.RunId {
			return fmt.Errorf("save acknowledgement run_id mismatch")
		}
		next := q.runs[1:]
		if err := q.write(next); err != nil {
			return err
		}
		q.runs = next
	}
	return nil
}
func (q *Queue) Len() int { q.mu.Lock(); defer q.mu.Unlock(); return len(q.runs) }
func (q *Queue) write(runs []*pb.Run) error {
	data, err := json.Marshal(runs)
	if err != nil {
		return err
	}
	dir := filepath.Dir(q.path)
	if err = os.MkdirAll(dir, 0700); err != nil {
		return err
	}
	file, err := os.CreateTemp(dir, ".pending-*.json")
	if err != nil {
		return err
	}
	defer os.Remove(file.Name())
	if _, err = file.Write(data); err != nil {
		file.Close()
		return err
	}
	if err = file.Sync(); err != nil {
		file.Close()
		return err
	}
	if err = file.Close(); err != nil {
		return err
	}
	return os.Rename(file.Name(), q.path)
}

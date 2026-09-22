package storage

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"path/filepath"
	"strings"

	_ "github.com/mattn/go-sqlite3"
	pb "night/gen/star/v1"
)

var ErrInvalidRun = errors.New("invalid completed run")

type Store struct{ db *sql.DB }

func Open(path string) (*Store, error) {
	absolute, err := filepath.Abs(path)
	if err != nil {
		return nil, err
	}
	u := url.URL{Scheme: "file", Path: absolute}
	db, err := sql.Open("sqlite3", u.String()+"?_busy_timeout=5000&_journal_mode=WAL&_synchronous=FULL")
	if err != nil {
		return nil, err
	}
	// One local writer also serializes idempotency checks and transactions.
	db.SetMaxOpenConns(1)
	_, err = db.Exec(`
 CREATE TABLE IF NOT EXISTS progress (
 level_id INTEGER PRIMARY KEY CHECK(level_id BETWEEN 1 AND 3),
 completed INTEGER NOT NULL CHECK(completed IN (0,1)),
 best_score INTEGER NOT NULL CHECK(best_score >= 0));
 CREATE TABLE IF NOT EXISTS runs (
 run_id TEXT PRIMARY KEY,
 level_id INTEGER NOT NULL CHECK(level_id BETWEEN 1 AND 3),
 score INTEGER NOT NULL CHECK(score >= 0),
 active_ms INTEGER NOT NULL CHECK(active_ms >= 0),
 action_counts_json TEXT NOT NULL);`)
	if err != nil {
		db.Close()
		return nil, err
	}
	return &Store{db: db}, nil
}
func (s *Store) Close() error { return s.db.Close() }
func ValidateRun(r *pb.Run) error {
	if r == nil || strings.TrimSpace(r.RunId) == "" || len(r.RunId) > 128 || r.LevelId < 1 || r.LevelId > 3 || r.Score < 0 || r.ActiveMs < 0 {
		return ErrInvalidRun
	}
	for action, count := range r.ActionCounts {
		if action < 1 || action > 6 || count < 0 {
			return ErrInvalidRun
		}
	}
	return nil
}
func (s *Store) Save(ctx context.Context, r *pb.Run) (*pb.Run, error) {
	if r == nil || strings.TrimSpace(r.RunId) == "" || len(r.RunId) > 128 {
		return nil, ErrInvalidRun
	}
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return nil, err
	}
	defer tx.Rollback()
	saved := &pb.Run{}
	var counts string
	err = tx.QueryRowContext(ctx, `SELECT run_id,level_id,score,active_ms,action_counts_json FROM runs WHERE run_id=?`, r.RunId).Scan(&saved.RunId, &saved.LevelId, &saved.Score, &saved.ActiveMs, &counts)
	if err == nil {
		if err = json.Unmarshal([]byte(counts), &saved.ActionCounts); err != nil {
			return nil, fmt.Errorf("read action counts: %w", err)
		}
		return saved, nil
	}
	if !errors.Is(err, sql.ErrNoRows) {
		return nil, err
	}
	if err := ValidateRun(r); err != nil {
		return nil, err
	}
	data, err := json.Marshal(r.ActionCounts)
	if err != nil {
		return nil, err
	}
	if _, err = tx.ExecContext(ctx, `INSERT INTO runs(run_id,level_id,score,active_ms,action_counts_json) VALUES(?,?,?,?,?)`, r.RunId, r.LevelId, r.Score, r.ActiveMs, string(data)); err != nil {
		return nil, err
	}
	if _, err = tx.ExecContext(ctx, `INSERT INTO progress(level_id,completed,best_score) VALUES(?,1,?) ON CONFLICT(level_id) DO UPDATE SET completed=1,best_score=MAX(progress.best_score,excluded.best_score)`, r.LevelId, r.Score); err != nil {
		return nil, err
	}
	if err = tx.Commit(); err != nil {
		return nil, err
	}
	// Return a detached value, just like a later retry read from SQLite.
	return &pb.Run{RunId: r.RunId, LevelId: r.LevelId, Score: r.Score, ActiveMs: r.ActiveMs, ActionCounts: cloneCounts(r.ActionCounts)}, nil
}
func cloneCounts(src map[int32]int64) map[int32]int64 {
	if src == nil {
		return nil
	}
	dst := make(map[int32]int64, len(src))
	for k, v := range src {
		dst[k] = v
	}
	return dst
}
func (s *Store) Progress(ctx context.Context) (*pb.GetProgressResponse, error) {
	result := &pb.GetProgressResponse{}
	for level := pb.Level(1); level <= 3; level++ {
		result.Levels = append(result.Levels, &pb.LevelProgress{LevelId: level})
	}
	rows, err := s.db.QueryContext(ctx, `SELECT level_id,completed,best_score FROM progress ORDER BY level_id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var level int
		var completed bool
		var score int64
		if err := rows.Scan(&level, &completed, &score); err != nil {
			return nil, err
		}
		result.Levels[level-1].Completed = completed
		result.Levels[level-1].BestScore = score
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	for i, p := range result.Levels {
		p.Unlocked = i == 0 || result.Levels[i-1].Completed
	}
	return result, nil
}

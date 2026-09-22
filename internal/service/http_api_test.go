package service

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"night/internal/storage"
)

func newTestMux(t *testing.T) *http.ServeMux {
	t.Helper()
	store, err := storage.Open(filepath.Join(t.TempDir(), "star.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = store.Close() })
	mux := http.NewServeMux()
	NewHTTPAPI(store).Register(mux)
	return mux
}

func doSave(t *testing.T, mux *http.ServeMux, body string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, "/api/save", bytes.NewBufferString(body))
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

func doProgress(t *testing.T, mux *http.ServeMux) (*httptest.ResponseRecorder, apiProgressResponse) {
	t.Helper()
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/progress", nil))
	var out apiProgressResponse
	if rec.Code == http.StatusOK {
		if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
			t.Fatal(err)
		}
	}
	return rec, out
}

func TestHTTPSaveIsIdempotentLikeSaveRun(t *testing.T) {
	mux := newTestMux(t)
	rec := doSave(t, mux, `{"run_id":"http-one","level_id":1,"score":100,"active_ms":2000,"action_counts":{"1":2,"6":1}}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("save status %d: %s", rec.Code, rec.Body.String())
	}
	var saved apiSaveResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &saved); err != nil {
		t.Fatal(err)
	}
	if saved.Run.RunID != "http-one" || saved.Run.Score != 100 || saved.Run.ActionCounts[6] != 1 || saved.Run.ActiveMs != 2000 {
		t.Fatalf("unexpected saved run: %+v", saved.Run)
	}

	// A retry with a different payload must return the original stored run and
	// must not move another level's progress.
	rec = doSave(t, mux, `{"run_id":"http-one","level_id":3,"score":999}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("retry status %d: %s", rec.Code, rec.Body.String())
	}
	var retried apiSaveResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &retried); err != nil {
		t.Fatal(err)
	}
	if retried.Run.LevelID != 1 || retried.Run.Score != 100 {
		t.Fatalf("retry changed the original run: %+v", retried.Run)
	}
	if _, progress := doProgress(t, mux); progress.Levels[2].Completed {
		t.Fatalf("retry leaked progress into level 3: %+v", progress.Levels)
	}
}

func TestHTTPRejectsInvalidRunAndBadJSON(t *testing.T) {
	mux := newTestMux(t)
	for name, body := range map[string]string{
		"level out of range": `{"run_id":"bad","level_id":4}`,
		"negative score":     `{"run_id":"bad","level_id":1,"score":-1}`,
		"empty run_id":       `{"run_id":"","level_id":1}`,
		"unknown action key": `{"run_id":"bad","level_id":1,"action_counts":{"0":1}}`,
		"unknown field":      `{"run_id":"bad","level_id":1,"typo":true}`,
		"malformed":          `{`,
	} {
		t.Run(name, func(t *testing.T) {
			if rec := doSave(t, mux, body); rec.Code != http.StatusBadRequest {
				t.Fatalf("want 400, got %d: %s", rec.Code, rec.Body.String())
			}
		})
	}
}

func TestHTTPProgressUnlocksNextLevel(t *testing.T) {
	mux := newTestMux(t)
	// Nothing saved yet: only level 1 is unlocked.
	rec, before := doProgress(t, mux)
	if rec.Code != http.StatusOK {
		t.Fatalf("progress status %d", rec.Code)
	}
	if len(before.Levels) != 3 || !before.Levels[0].Unlocked || before.Levels[1].Unlocked || before.Levels[2].Unlocked {
		t.Fatalf("unexpected initial progress: %+v", before.Levels)
	}
	if rec := doSave(t, mux, `{"run_id":"clear-1","level_id":1,"score":42}`); rec.Code != http.StatusOK {
		t.Fatalf("save failed: %d", rec.Code)
	}
	_, after := doProgress(t, mux)
	if !after.Levels[0].Completed || after.Levels[0].BestScore != 42 || !after.Levels[1].Unlocked {
		t.Fatalf("progress did not advance: %+v", after.Levels)
	}
}

func TestHTTPMethodGuards(t *testing.T) {
	mux := newTestMux(t)
	// A wrong verb is rejected, never treated as an empty save.
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/save", nil))
	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("want 405 for GET /api/save, got %d", rec.Code)
	}
	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodPost, "/api/progress", nil))
	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("want 405 for POST /api/progress, got %d", rec.Code)
	}
}

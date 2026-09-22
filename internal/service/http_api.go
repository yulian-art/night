package service

import (
	"encoding/json"
	"net/http"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	pb "night/gen/star/v1"
	"night/internal/storage"
)

// HTTPAPI serves the save chain over plain HTTP+JSON, so UE (which has no gRPC
// plugin) can settle runs and read progress. Semantics mirror SaveRun and
// GetProgress exactly; only the transport differs. Both paths call the same
// storage.Store and classify failures through the same storageError, so the
// HTTP surface can never drift from the gRPC one.
const apiMaxBodyBytes = 64 * 1024 // matches the gRPC MaxRecvMsgSize

type HTTPAPI struct{ store *storage.Store }

func NewHTTPAPI(store *storage.Store) *HTTPAPI { return &HTTPAPI{store: store} }

// Register mounts the save endpoints. Method-qualified patterns give a 405 for
// a wrong verb without an explicit check inside each handler.
func (a *HTTPAPI) Register(mux *http.ServeMux) {
	mux.HandleFunc("POST /api/save", a.save)
	mux.HandleFunc("GET /api/progress", a.progress)
}

// apiRun is the JSON wire form of star.v1.Run. Field names match the proto so
// UE and Python read one contract; action_counts keys are decimal action
// values, marshalled by encoding/json as strings.
type apiRun struct {
	RunID        string          `json:"run_id"`
	LevelID      int32           `json:"level_id"`
	Score        int64           `json:"score"`
	ActiveMs     int64           `json:"active_ms"`
	ActionCounts map[int32]int64 `json:"action_counts"`
}

type apiSaveResponse struct {
	Run apiRun `json:"run"`
}

type apiLevelProgress struct {
	LevelID   int32 `json:"level_id"`
	Completed bool  `json:"completed"`
	BestScore int64 `json:"best_score"`
	Unlocked  bool  `json:"unlocked"`
}

type apiProgressResponse struct {
	Levels []apiLevelProgress `json:"levels"`
}

type apiError struct {
	Error string `json:"error"`
	Code  string `json:"code"`
}

// toProto converts the wire form to the domain message. Field names already
// match, so this is a direct mapping with no defaults invented.
func (r apiRun) toProto() *pb.Run {
	return &pb.Run{
		RunId:        r.RunID,
		LevelId:      pb.Level(r.LevelID),
		Score:        r.Score,
		ActiveMs:     r.ActiveMs,
		ActionCounts: r.ActionCounts,
	}
}

func fromProto(run *pb.Run) apiRun {
	return apiRun{
		RunID:        run.GetRunId(),
		LevelID:      int32(run.GetLevelId()),
		Score:        run.GetScore(),
		ActiveMs:     run.GetActiveMs(),
		ActionCounts: run.GetActionCounts(),
	}
}

// save is the HTTP equivalent of SaveRun. A repeated run_id returns the run
// stored first, even if this payload differs — the retry-safety rule the
// client outbox depends on.
func (a *HTTPAPI) save(w http.ResponseWriter, r *http.Request) {
	var body apiRun
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, apiMaxBodyBytes))
	// Reject unknown fields: a typo must not silently save a wrong run. This
	// matches the recognizer config loader, which refuses unknown keys too.
	dec.DisallowUnknownFields()
	if err := dec.Decode(&body); err != nil {
		writeAPIError(w, http.StatusBadRequest, "invalid_argument", "invalid JSON body")
		return
	}
	saved, err := a.store.Save(r.Context(), body.toProto())
	if err != nil {
		code, name, message := apiErrorFor(err)
		writeAPIError(w, code, name, message)
		return
	}
	writeAPIJSON(w, http.StatusOK, apiSaveResponse{Run: fromProto(saved)})
}

// progress is the HTTP equivalent of GetProgress.
func (a *HTTPAPI) progress(w http.ResponseWriter, r *http.Request) {
	result, err := a.store.Progress(r.Context())
	if err != nil {
		code, name, message := apiErrorFor(err)
		writeAPIError(w, code, name, message)
		return
	}
	levels := result.GetLevels()
	out := apiProgressResponse{Levels: make([]apiLevelProgress, 0, len(levels))}
	for _, level := range levels {
		out.Levels = append(out.Levels, apiLevelProgress{
			LevelID:   int32(level.GetLevelId()),
			Completed: level.GetCompleted(),
			BestScore: level.GetBestScore(),
			Unlocked:  level.GetUnlocked(),
		})
	}
	writeAPIJSON(w, http.StatusOK, out)
}

// apiErrorFor classifies a storage failure by running it through storageError,
// so HTTP and gRPC agree on what counts as a client error and internal details
// are never leaked to the caller.
func apiErrorFor(err error) (httpCode int, code, message string) {
	grpcErr := storageError(err)
	switch status.Code(grpcErr) {
	case codes.InvalidArgument:
		return http.StatusBadRequest, "invalid_argument", grpcErr.Error()
	case codes.Canceled:
		return http.StatusRequestTimeout, "canceled", grpcErr.Error()
	case codes.DeadlineExceeded:
		return http.StatusGatewayTimeout, "deadline_exceeded", grpcErr.Error()
	default:
		return http.StatusInternalServerError, "internal", grpcErr.Error()
	}
}

func writeAPIJSON(w http.ResponseWriter, code int, payload any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeAPIError(w http.ResponseWriter, code int, name, message string) {
	writeAPIJSON(w, code, apiError{Error: message, Code: name})
}

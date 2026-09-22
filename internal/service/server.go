package service

import (
	"context"
	"errors"
	"io"
	"log/slog"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	pb "night/gen/star/v1"
	"night/internal/input"
	"night/internal/storage"
)

type Server struct {
	pb.UnimplementedStarServiceServer
	pb.UnimplementedRecognizerServiceServer
	hub   *input.Hub
	store *storage.Store
}

func New(hub *input.Hub, store *storage.Store) *Server { return &Server{hub: hub, store: store} }
func (s *Server) WatchInput(req *pb.WatchInputRequest, stream grpc.ServerStreamingServer[pb.InputEvent]) error {
	sub, err := s.hub.Subscribe(req.Generation)
	if err != nil {
		return err
	}
	defer s.hub.Unsubscribe(sub)
	for {
		select {
		case <-sub.Done:
			return sub.Err()
		default:
		}
		select {
		case <-stream.Context().Done():
			return status.FromContextError(stream.Context().Err()).Err()
		case <-sub.Done:
			return sub.Err()
		case event := <-sub.Events:
			select {
			case <-sub.Done:
				return sub.Err()
			default:
			}
			if err := stream.Send(event); err != nil {
				return err
			}
		}
	}
}
func (s *Server) Connect(stream grpc.BidiStreamingServer[pb.InputEvent, pb.ResetInput]) error {
	producer, err := s.hub.Attach()
	if err != nil {
		return err
	}
	defer s.hub.Detach(producer)
	received := make(chan error, 1)
	// gRPC releases Recv when the handler returns; buffered result cannot leak.
	go func() {
		for {
			event, err := stream.Recv()
			if err != nil {
				received <- err
				return
			}
			if err = s.hub.Publish(producer, event); err != nil {
				received <- err
				return
			}
		}
	}()
	for {
		select {
		case <-stream.Context().Done():
			return status.FromContextError(stream.Context().Err()).Err()
		case err := <-received:
			if errors.Is(err, io.EOF) {
				return nil
			}
			return err
		case generation := <-producer.Resets:
			if err := stream.Send(&pb.ResetInput{Generation: generation}); err != nil {
				return err
			}
		}
	}
}
func (s *Server) SaveRun(ctx context.Context, req *pb.SaveRunRequest) (*pb.SaveRunResponse, error) {
	run, err := s.store.Save(ctx, req.GetRun())
	if err != nil {
		return nil, storageError(err)
	}
	return &pb.SaveRunResponse{Run: run}, nil
}
func (s *Server) GetProgress(ctx context.Context, _ *pb.GetProgressRequest) (*pb.GetProgressResponse, error) {
	result, err := s.store.Progress(ctx)
	if err != nil {
		return nil, storageError(err)
	}
	return result, nil
}
func storageError(err error) error {
	if errors.Is(err, storage.ErrInvalidRun) {
		return status.Error(codes.InvalidArgument, err.Error())
	}
	if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
		return status.FromContextError(err).Err()
	}
	slog.Error("storage operation failed", "error", err)
	return status.Error(codes.Internal, "storage operation failed; retry SaveRun with the same run_id")
}

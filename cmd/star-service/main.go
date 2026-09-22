package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	pb "night/gen/star/v1"
	"night/internal/input"
	"night/internal/service"
	"night/internal/storage"
)

func main() {
	if err := run(); err != nil {
		slog.Error("service stopped", "error", err)
		os.Exit(1)
	}
}

// mustLoopback resolves a listen address and rejects anything but a loopback
// IP, so neither the gRPC nor the WebSocket endpoint is ever exposed off-box.
func mustLoopback(address string) error {
	host, _, err := net.SplitHostPort(address)
	if err != nil {
		return err
	}
	ip := net.ParseIP(host)
	if ip == nil || !ip.IsLoopback() {
		return fmt.Errorf("listen address must use a loopback IP")
	}
	return nil
}

func run() error {
	address := flag.String("listen", "127.0.0.1:50051", "loopback gRPC address")
	wsAddress := flag.String("ws-listen", "127.0.0.1:50052", "loopback WebSocket/JSON address for UE")
	database := flag.String("db", "data/star.db", "SQLite database path")
	capacity := flag.Int("queue-capacity", 64, "maximum pending input events")
	flag.Parse()
	if err := mustLoopback(*address); err != nil {
		return err
	}
	if err := mustLoopback(*wsAddress); err != nil {
		return err
	}
	if *capacity < 1 {
		return fmt.Errorf("queue-capacity must be positive")
	}
	if err := os.MkdirAll(filepath.Dir(*database), 0700); err != nil {
		return err
	}
	store, err := storage.Open(*database)
	if err != nil {
		return err
	}
	defer store.Close()

	// One Hub feeds both transports: gRPC (Python recognizer + any gRPC UE
	// client) and the WebSocket/JSON gateway (UE without a gRPC plugin).
	hub := input.New(*capacity)
	implementation := service.New(hub, store)

	grpcListener, err := net.Listen("tcp", *address)
	if err != nil {
		return err
	}
	defer grpcListener.Close()
	grpcServer := grpc.NewServer(grpc.MaxRecvMsgSize(64 * 1024))
	pb.RegisterStarServiceServer(grpcServer, implementation)
	pb.RegisterRecognizerServiceServer(grpcServer, implementation)
	healthServer := health.NewServer()
	healthpb.RegisterHealthServer(grpcServer, healthServer)
	healthServer.SetServingStatus("", healthpb.HealthCheckResponse_SERVING)

	// WebSocket gateway on its own loopback listener.
	wsListener, err := net.Listen("tcp", *wsAddress)
	if err != nil {
		return err
	}
	defer wsListener.Close()
	mux := http.NewServeMux()
	mux.Handle("/ws/input", service.NewWSGateway(hub))
	// Save chain over HTTP+JSON, for the same reason as the WebSocket gateway:
	// UE has no gRPC plugin. Both transports share one storage.Store.
	service.NewHTTPAPI(store).Register(mux)
	httpServer := &http.Server{Handler: mux, ReadHeaderTimeout: 5 * time.Second}

	signals := make(chan os.Signal, 1)
	signal.Notify(signals, os.Interrupt, syscall.SIGTERM)
	defer signal.Stop(signals)
	stopped := make(chan struct{})
	defer close(stopped)
	go func() {
		select {
		case <-signals:
		case <-stopped:
			return
		}
		healthServer.Shutdown()
		timer := time.AfterFunc(3*time.Second, grpcServer.Stop)
		defer timer.Stop()
		grpcServer.GracefulStop()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		_ = httpServer.Shutdown(shutdownCtx)
	}()

	// Run both servers; return the first non-graceful error.
	errs := make(chan error, 2)
	go func() { errs <- httpServer.Serve(wsListener) }()
	go func() { errs <- grpcServer.Serve(grpcListener) }()
	slog.Info("star service listening",
		"grpc", grpcListener.Addr(), "websocket", wsListener.Addr(), "database", *database)
	// Whichever server stops first (signal-triggered graceful stop or a hard
	// failure), shut the other down too so we never leave one serving alone.
	err = <-errs
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	_ = httpServer.Shutdown(shutdownCtx)
	grpcServer.GracefulStop()
	if errors.Is(err, http.ErrServerClosed) {
		return nil
	}
	return err
}

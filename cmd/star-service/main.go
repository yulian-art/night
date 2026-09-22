package main

import (
	"flag"
	"fmt"
	"log/slog"
	"net"
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
func run() error {
	address := flag.String("listen", "127.0.0.1:50051", "loopback gRPC address")
	database := flag.String("db", "data/star.db", "SQLite database path")
	capacity := flag.Int("queue-capacity", 64, "maximum pending input events")
	flag.Parse()
	host, _, err := net.SplitHostPort(*address)
	if err != nil {
		return err
	}
	ip := net.ParseIP(host)
	if ip == nil || !ip.IsLoopback() {
		return fmt.Errorf("listen address must use a loopback IP")
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
	listener, err := net.Listen("tcp", *address)
	if err != nil {
		return err
	}
	defer listener.Close()
	server := grpc.NewServer(grpc.MaxRecvMsgSize(64 * 1024))
	implementation := service.New(input.New(*capacity), store)
	pb.RegisterStarServiceServer(server, implementation)
	pb.RegisterRecognizerServiceServer(server, implementation)
	healthServer := health.NewServer()
	healthpb.RegisterHealthServer(server, healthServer)
	healthServer.SetServingStatus("", healthpb.HealthCheckResponse_SERVING)
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
		timer := time.AfterFunc(3*time.Second, server.Stop)
		defer timer.Stop()
		server.GracefulStop()
	}()
	slog.Info("star service listening", "address", listener.Addr(), "database", *database)
	return server.Serve(listener)
}

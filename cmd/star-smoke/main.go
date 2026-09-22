// star-smoke checks the local adapter without camera access or real save writes.
package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	pb "night/gen/star/v1"
)

func main() {
	address := flag.String("address", "127.0.0.1:50051", "local service address")
	generation := flag.Uint64("generation", uint64(time.Now().UnixNano()), "fresh generation greater than previous UE generation")
	flag.Parse()
	if err := run(*address, *generation); err != nil {
		log.Fatal(err)
	}
}
func run(address string, generation uint64) error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	connection, err := grpc.NewClient(address, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return err
	}
	defer connection.Close()
	recognizer, err := pb.NewRecognizerServiceClient(connection).Connect(ctx)
	if err != nil {
		return err
	}
	if _, err = recognizer.Recv(); err != nil {
		return err
	}
	client := pb.NewStarServiceClient(connection)
	stream, err := client.WatchInput(ctx, &pb.WatchInputRequest{Generation: generation})
	if err != nil {
		return err
	}
	if _, err = stream.Recv(); err != nil {
		return err
	} // initial NotReady
	for {
		reset, err := recognizer.Recv()
		if err != nil {
			return err
		}
		if reset.Generation == generation {
			break
		}
	}
	events := []*pb.InputEvent{
		{Event: &pb.InputEvent_Tracking{Tracking: &pb.TrackingEvent{Generation: generation, State: pb.TrackingState_TRACKING_STATE_READY}}},
		{Event: &pb.InputEvent_Action{Action: &pb.ActionEvent{Generation: generation, Action: pb.Action_ACTION_JUMPING_JACK, Phase: pb.Phase_PHASE_BEGIN}}},
		{Event: &pb.InputEvent_Action{Action: &pb.ActionEvent{Generation: generation, Action: pb.Action_ACTION_JUMPING_JACK, Phase: pb.Phase_PHASE_COMPLETE}}},
		{Event: &pb.InputEvent_Tracking{Tracking: &pb.TrackingEvent{Generation: generation, State: pb.TrackingState_TRACKING_STATE_READY}}},
	}
	for _, event := range events {
		if err := recognizer.Send(event); err != nil {
			return err
		}
		got, err := stream.Recv()
		if err != nil {
			return err
		}
		fmt.Println(got)
	}
	progress, err := client.GetProgress(ctx, &pb.GetProgressRequest{})
	if err != nil {
		return err
	}
	fmt.Println(progress)
	return nil
}

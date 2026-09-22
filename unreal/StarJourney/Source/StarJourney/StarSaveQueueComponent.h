// Copyright 向星而行. Durable outbox for completed runs (UE port of client/savequeue).
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "StarTypes.h"
#include "StarSaveQueueComponent.generated.h"

// One completed gameplay run. Mirrors star.v1.Run exactly.
USTRUCT(BlueprintType)
struct FStarRun
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite, Category = "Star|Save")
	FString RunId;

	UPROPERTY(BlueprintReadWrite, Category = "Star|Save")
	int32 LevelId = 0;

	UPROPERTY(BlueprintReadWrite, Category = "Star|Save")
	int64 Score = 0;

	UPROPERTY(BlueprintReadWrite, Category = "Star|Save")
	int64 ActiveMs = 0;

	// Keys are numeric Action values 1..6; values are completed cycles.
	UPROPERTY(BlueprintReadWrite, Category = "Star|Save")
	TMap<int32, int64> ActionCounts;
};

// One level's derived progress, mirroring star.v1.LevelProgress.
USTRUCT(BlueprintType)
struct FStarLevelProgress
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Star|Save")
	int32 LevelId = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Star|Save")
	bool bCompleted = false;

	UPROPERTY(BlueprintReadOnly, Category = "Star|Save")
	int64 BestScore = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Star|Save")
	bool bUnlocked = false;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FStarFlushFinished, bool, bSucceeded);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FStarProgressLoaded, bool, bSucceeded);

// Client half of the save chain: a durable local outbox plus a progress reader,
// both talking to the Go service over HTTP+JSON (UE has no gRPC plugin).
//
// The outbox rules are ported from client/savequeue on the Go side and must stay
// identical:
//   - Enqueue BEFORE any send, and persist before returning, so a crash or a
//     failed request can never lose a completed run.
//   - Remove a record only when the server acknowledges the SAME run_id, so a
//     committed save whose reply was lost is retried with the same id and the
//     store's idempotency returns the original run.
//   - A corrupt pending file is reported, never silently replaced with an
//     empty queue.
//   - Flush stops at the first failure and keeps the remaining records.
//
// The queue is owned by one process; do not share the file with another writer.
UCLASS(ClassGroup = (Star), meta = (BlueprintSpawnableComponent))
class STARJOURNEY_API UStarSaveQueueComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UStarSaveQueueComponent();

	virtual void BeginPlay() override;

	// Base URL of the Go service HTTP API (the -ws-listen port).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Save")
	FString ServiceBaseUrl = TEXT("http://127.0.0.1:50052");

	// Pending list path; relative paths resolve under ProjectSavedDir.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Save")
	FString PendingFileName = TEXT("StarJourney/pending-runs.json");

	// Read the pending list from disk. Returns false only for a corrupt file
	// (missing file is a valid empty queue). Nothing is sent here.
	UFUNCTION(BlueprintCallable, Category = "Star|Save")
	bool LoadPending();

	// Append a completed run and persist it immediately. Duplicate run_ids are
	// ignored, matching the server's idempotency.
	UFUNCTION(BlueprintCallable, Category = "Star|Save")
	bool Enqueue(const FStarRun& Run);

	// Send pending runs in order, stopping at the first failure.
	UFUNCTION(BlueprintCallable, Category = "Star|Save")
	void Flush();

	// Read level progress (drives unlock). Safe before any save exists.
	UFUNCTION(BlueprintCallable, Category = "Star|Save")
	void FetchProgress();

	UFUNCTION(BlueprintPure, Category = "Star|Save")
	int32 NumPending() const { return Pending.Num(); }

	// True once the pending file loaded cleanly and no send is in flight.
	UFUNCTION(BlueprintPure, Category = "Star|Save")
	bool IsIdle() const { return !bFlushActive; }

	// Fired when a flush pass finishes (true only if the queue drained).
	UPROPERTY(BlueprintAssignable, Category = "Star|Save")
	FStarFlushFinished OnFlushFinished;

	// Fired after a progress read attempt.
	UPROPERTY(BlueprintAssignable, Category = "Star|Save")
	FStarProgressLoaded OnProgressLoaded;

	// Last progress read; empty until FetchProgress succeeds.
	UPROPERTY(BlueprintReadOnly, Category = "Star|Save")
	TArray<FStarLevelProgress> Progress;

private:
	// Serialize Runs and replace the file via a temp file + atomic move.
	// Serialization happens first so a failure cannot truncate the live file.
	bool WriteAtomic(const TArray<FStarRun>& Runs);

	FString ResolvePath() const;

	void SendNext();
	void OnSaveResponse(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bConnectedSuccessfully);
	void OnProgressResponse(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bConnectedSuccessfully);

	// Build the star.v1.Run JSON body for one run.
	FString BuildRunJson(const FStarRun& Run) const;

	TArray<FStarRun> Pending;

	// Flush state. bFlushActive guards against overlapping passes.
	bool bFlushActive = false;
	FString InFlightRunId;
	bool bProgressRequestActive = false;
};

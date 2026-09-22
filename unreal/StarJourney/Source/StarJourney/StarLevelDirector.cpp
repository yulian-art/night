// Copyright 向星而行. Level controller: fixed route, task stops, scoring, seed.
#include "StarLevelDirector.h"

#include "StarRunnerPawn.h"
#include "StarSaveQueueComponent.h"
#include "StarStation.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"

AStarLevelDirector::AStarLevelDirector()
{
	PrimaryActorTick.bCanEverTick = true;
	SaveQueue = CreateDefaultSubobject<UStarSaveQueueComponent>(TEXT("SaveQueue"));
}

void AStarLevelDirector::BeginPlay()
{
	Super::BeginPlay();
}

void AStarLevelDirector::InitializeRun(AStarRunnerPawn* InRunner, const TArray<AStarStation*>& InStations)
{
	Runner = InRunner;
	Stations = InStations;
	// Sort stations by StopX so progression follows the route forward.
	Stations.Sort([](const AStarStation& A, const AStarStation& B) { return A.StopX < B.StopX; });
	NextStation = 0;
	CompletedCount = 0;
	Starlight = 0;
	bWaitingAtStation = false;
	bLevelComplete = false;
	ActionCounts.Empty();
	// Start the active-time clock for Run.active_ms.
	RunStartedAtSeconds = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	if (Runner)
	{
		Runner->OnActionCompleted.RemoveAll(this);
		Runner->OnActionCompleted.AddDynamic(this, &AStarLevelDirector::NotifyActionCompleted);
		Runner->SetRunning(true);
	}
	// Last, once the run is fully wired, whether by hand/Blueprint or by
	// auto-init. This is what stops Tick from discovering a second roster and
	// re-running over a live run.
	bInitialized = true;
}

int32 AStarLevelDirector::GetActionCount(EStarAction Action) const
{
	const int32* Found = ActionCounts.Find(Action);
	return Found ? *Found : 0;
}

EStarAction AStarLevelDirector::GetRequiredActionNow() const
{
	// Defined in the .cpp rather than inline in the header because AStarStation
	// is only forward-declared there, and the prompt needs the complete type.
	if (!bWaitingAtStation || !Stations.IsValidIndex(NextStation))
	{
		// Outside a stop the player may perform any action the lane allows, so
		// there is nothing specific to prompt.
		return EStarAction::None;
	}
	AStarStation* Station = Stations[NextStation];
	return Station ? Station->GetRequiredAction() : EStarAction::None;
}

int32 AStarLevelDirector::GetNextStationIndex() const
{
	return NextStation;
}

void AStarLevelDirector::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Playable levels are produced by a generator that only places actors and
	// sets properties - no Blueprint wires InitializeRun - so the director
	// finds its own runner and stations. This cannot happen in BeginPlay: the
	// GameMode spawns and possesses the pawn on its own schedule, so on the
	// first Tick the director may legitimately see no pawn yet. Hence the retry.
	if (bAutoInitialize && !bInitialized)
	{
		TryAutoInitialize();
		// Still unwired (no player pawn or no stations yet): there is nothing
		// to drive, so leave before touching UpdateStops.
		if (!bInitialized)
		{
			return;
		}
	}

	if (!Runner || bLevelComplete)
	{
		return;
	}
	UpdateStops();
}

// Two cheap lookups per attempt, repeated until both halves exist; the retry
// is what makes a late-spawned player pawn a non-issue instead of a race the
// level has to win on frame one.
void AStarLevelDirector::TryAutoInitialize()
{
	if (!GetWorld())
	{
		return;
	}

	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	AStarRunnerPawn* Pawn = PC ? Cast<AStarRunnerPawn>(PC->GetPawn()) : nullptr;

	// TActorIterator walks the level's actor list directly, so no temporary
	// AActor* array and no cast pass is needed for the stations.
	TArray<AStarStation*> FoundStations;
	for (TActorIterator<AStarStation> It(GetWorld()); It; ++It)
	{
		FoundStations.Add(*It);
	}

	if (Pawn && FoundStations.Num() > 0)
	{
		// InitializeRun stays the single entry point: it sorts by StopX and
		// resets every counter, so the roster must never be assembled twice by
		// hand here.
		InitializeRun(Pawn, FoundStations);
	}
	// Fewer than one station means the level content is not up yet. Waiting
	// beats wiring an empty run, which would find no stop and settle instantly
	// at FinishX the moment the runner crossed it.
}

// Clamp the stop to the task point: a dropped frame must not skip it. The
// runner eases to a halt just before StopX and waits for the required cycle.
void AStarLevelDirector::UpdateStops()
{
	if (!Stations.IsValidIndex(NextStation))
	{
		// All stations handled; settle once the finish line is crossed.
		if (Runner->GetActorLocation().X >= FinishX)
		{
			Settle();
		}
		return;
	}

	AStarStation* Station = Stations[NextStation];
	const float X = Runner->GetActorLocation().X;

	if (!bWaitingAtStation)
	{
		if (X >= Station->StopX - StopApproachDistance)
		{
			// Hard clamp: pin to the approach point and stop forward motion.
			FVector Loc = Runner->GetActorLocation();
			if (Loc.X > Station->StopX)
			{
				Loc.X = Station->StopX;
				Runner->SetActorLocation(Loc);
			}
			Runner->SetRunning(false);
			bWaitingAtStation = true;
		}
	}
	else
	{
		// Hold position exactly at the stop while waiting for the action.
		FVector Loc = Runner->GetActorLocation();
		if (Loc.X != Station->StopX)
		{
			Loc.X = Station->StopX;
			Runner->SetActorLocation(Loc);
		}
	}
}

void AStarLevelDirector::NotifyActionCompleted(EStarAction Action)
{
	if (bLevelComplete || Action == EStarAction::None)
	{
		return;
	}
	// Count every completed cycle (documented: counts represent completed
	// cycles, never Begin or Cancel).
	ActionCounts.FindOrAdd(Action)++;

	if (!bWaitingAtStation || !Stations.IsValidIndex(NextStation))
	{
		return;
	}

	AStarStation* Station = Stations[NextStation];
	if (Station->OfferAction(Action))
	{
		if (Station->IsComplete())
		{
			CompletedCount++;
			Starlight++;
			OnStationLit(NextStation, CompletedCount);
			NextStation++;
			bWaitingAtStation = false;
			// Resume forward motion toward the next station / finish.
			if (Runner)
			{
				Runner->SetRunning(true);
			}
		}
	}
}

void AStarLevelDirector::Settle()
{
	if (bLevelComplete)
	{
		return;
	}
	bLevelComplete = true;
	if (Runner)
	{
		Runner->SetRunning(false);
	}
	// Persist the result before presenting the finale: the outbox enqueues
	// durably first, so even a crash during the celebration cannot lose it.
	SaveSettledRun();
	OnLevelSettled(Starlight);
}

void AStarLevelDirector::SaveSettledRun()
{
	if (!SaveQueue)
	{
		return;
	}

	FStarRun Run;
	// One id per settled run, generated once here and reused by every retry:
	// if the service commits but the reply is lost, the retry returns the
	// original record instead of writing a second one.
	Run.RunId = FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphens);
	Run.LevelId = LevelId;
	Run.Score = Starlight;

	const double Now = GetWorld() ? GetWorld()->GetTimeSeconds() : RunStartedAtSeconds;
	Run.ActiveMs = (int64)FMath::Max(0.0, (Now - RunStartedAtSeconds) * 1000.0);

	for (const TPair<EStarAction, int32>& Pair : ActionCounts)
	{
		// Keys are the numeric Action values 1..6; EStarAction mirrors the proto
		// so no lookup table is needed.
		if (Pair.Value > 0)
		{
			Run.ActionCounts.Add((int32)Pair.Key, (int64)Pair.Value);
		}
	}

	if (SaveQueue->Enqueue(Run))
	{
		SaveQueue->Flush();
	}
	else
	{
		UE_LOG(LogTemp, Error,
			TEXT("StarJourney: could not enqueue the settled run; the result was not saved"));
	}
}

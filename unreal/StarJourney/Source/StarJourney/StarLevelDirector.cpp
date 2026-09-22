// Copyright 向星而行. Level controller: fixed route, task stops, scoring, seed.
#include "StarLevelDirector.h"

#include "StarRunnerPawn.h"
#include "StarStation.h"

AStarLevelDirector::AStarLevelDirector()
{
	PrimaryActorTick.bCanEverTick = true;
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
	if (Runner)
	{
		Runner->OnActionCompleted.RemoveAll(this);
		Runner->OnActionCompleted.AddDynamic(this, &AStarLevelDirector::NotifyActionCompleted);
		Runner->SetRunning(true);
	}
}

int32 AStarLevelDirector::GetActionCount(EStarAction Action) const
{
	const int32* Found = ActionCounts.Find(Action);
	return Found ? *Found : 0;
}

void AStarLevelDirector::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!Runner || bLevelComplete)
	{
		return;
	}
	UpdateStops();
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
	OnLevelSettled(Starlight);
}

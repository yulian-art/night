// Copyright 向星而行. HUD host: builds the Slate overlay and feeds it state.
#include "StarHUD.h"

#include "StarHudWidget.h"
#include "StarLevelDirector.h"
#include "StarRunnerPawn.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"

AStarHUD::AStarHUD()
{
	PrimaryActorTick.bCanEverTick = true;
	// 暂停时仍需刷新，否则界面停在被暂停前的最后一帧，看不到"已暂停"提示。
	PrimaryActorTick.bTickEvenWhenPaused = true;
}

void AStarHUD::BeginPlay()
{
	Super::BeginPlay();

	if (!GEngine || !GEngine->GameViewport)
	{
		return;
	}
	// A viewport widget rather than a UMG widget: the whole HUD is code, so it
	// lives in version control (see StarHudWidget.h).
	SAssignNew(HudWidget, SStarHudWidget);
	if (HudWidget.IsValid())
	{
		GEngine->GameViewport->AddViewportWidgetContent(HudWidget.ToSharedRef(), 10);
	}
}

void AStarHUD::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (HudWidget.IsValid() && GEngine && GEngine->GameViewport)
	{
		GEngine->GameViewport->RemoveViewportWidgetContent(HudWidget.ToSharedRef());
	}
	HudWidget.Reset();
	Super::EndPlay(EndPlayReason);
}

void AStarHUD::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	RefreshFromWorld();
}

AStarRunnerPawn* AStarHUD::FindRunner()
{
	if (CachedRunner.IsValid())
	{
		return CachedRunner.Get();
	}
	AStarRunnerPawn* Runner = Cast<AStarRunnerPawn>(UGameplayStatics::GetPlayerPawn(this, 0));
	CachedRunner = Runner;
	return Runner;
}

AStarLevelDirector* AStarHUD::FindDirector()
{
	if (CachedDirector.IsValid())
	{
		return CachedDirector.Get();
	}
	if (UWorld* World = GetWorld())
	{
		for (TActorIterator<AStarLevelDirector> It(World); It; ++It)
		{
			CachedDirector = *It;
			return *It;
		}
	}
	return nullptr;
}

void AStarHUD::RefreshFromWorld()
{
	if (!HudWidget.IsValid())
	{
		return;
	}

	FStarHudState State;

	if (AStarRunnerPawn* Runner = FindRunner())
	{
		State.CurrentAction = Runner->GetActiveAction();
		State.Tracking = Runner->GetTracking();
	}
	if (AStarLevelDirector* Director = FindDirector())
	{
		State.Starlight = Director->GetStarlight();
		State.CompletedTasks = Director->GetCompletedCount();
		State.TotalTasks = Director->GetTotalStations();
		State.bLevelComplete = Director->IsLevelComplete();
		State.bWaitingAtStation = Director->IsWaitingAtStation();
		State.RequiredAction = Director->GetRequiredActionNow();
	}

	// Read the engine's own pause state so the overlay cannot disagree with it.
	State.bPaused = UGameplayStatics::IsGamePaused(this);

	HudWidget->Refresh(State);
}

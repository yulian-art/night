// Copyright 向星而行. Generic task station.
#include "StarStation.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/PointLightComponent.h"

AStarStation::AStarStation()
{
	PrimaryActorTick.bCanEverTick = false;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;

	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	Mesh->SetupAttachment(Root);

	Glow = CreateDefaultSubobject<UPointLightComponent>(TEXT("Glow"));
	Glow->SetupAttachment(Root);
	Glow->SetIntensity(5.0f);
	Glow->SetLightColor(LitColor);
	Glow->SetAttenuationRadius(700.0f);
	Glow->CastShadows = false;
}

void AStarStation::BeginPlay()
{
	Super::BeginPlay();
	Glow->SetLightColor(LitColor);
	SetGlow(5.0f);
}

EStarAction AStarStation::GetRequiredAction() const
{
	if (bComplete || !RequiredSteps.IsValidIndex(NextStep))
	{
		return EStarAction::None;
	}
	return RequiredSteps[NextStep];
}

bool AStarStation::OfferAction(EStarAction Action)
{
	if (bComplete || Action == EStarAction::None)
	{
		return false;
	}
	// Steps must be offered in order.
	if (GetRequiredAction() != Action)
	{
		return false;
	}
	NextStep++;
	if (NextStep >= RequiredSteps.Num())
	{
		bComplete = true;
		SetGlow(LitIntensity);
		OnLit();
	}
	return true;
}

void AStarStation::SetGlow(float Intensity)
{
	if (Glow)
	{
		Glow->SetIntensity(Intensity);
	}
}

// Copyright 向星而行. Unified action input: keyboard now, WebSocket gestures next.
#include "StarInputComponent.h"

#include "StarRunnerPawn.h"
#include "Components/InputComponent.h"
#include "InputCoreTypes.h"
#include "IWebSocket.h"
#include "WebSocketsModule.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

UStarInputComponent::UStarInputComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

void UStarInputComponent::BeginPlay()
{
	Super::BeginPlay();
	CachedRunner = Cast<AStarRunnerPawn>(GetOwner());
	Generation = NextGeneration();
}

void UStarInputComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	DisconnectGestures();
	Super::EndPlay(EndPlayReason);
}

AStarRunnerPawn* UStarInputComponent::Runner() const
{
	return CachedRunner;
}

uint64 UStarInputComponent::NextGeneration()
{
	// Unix-nanos from total ticks (100ns units); strictly increasing for a live
	// process, matching star-smoke's scheme. FDateTime ticks are 100ns since
	// 0001-01-01; the Unix epoch offset is 62135596800 seconds.
	const int64 UnixTicks = FDateTime::UtcNow().GetTicks() - 621355968000000000LL;
	return (uint64)UnixTicks * 100u;
}

// ---------------------------------------------------------------------------
// Keyboard source. A physical action is a Begin on press; for held actions
// (squat, legs) the Complete fires on release; for taps (jumps, jack) the
// runner's own arc completes the cycle and we emit Begin+Complete together.
// ---------------------------------------------------------------------------

void UStarInputComponent::BindKeyboard(UInputComponent* PlayerInputComponent)
{
	if (!PlayerInputComponent)
	{
		return;
	}
	PlayerInputComponent->BindKey(EKeys::A, IE_Pressed, this, &UStarInputComponent::OnJumpLeftPressed);
	PlayerInputComponent->BindKey(EKeys::D, IE_Pressed, this, &UStarInputComponent::OnJumpRightPressed);
	PlayerInputComponent->BindKey(EKeys::S, IE_Pressed, this, &UStarInputComponent::OnSquatPressed);
	PlayerInputComponent->BindKey(EKeys::S, IE_Released, this, &UStarInputComponent::OnSquatReleased);
	PlayerInputComponent->BindKey(EKeys::SpaceBar, IE_Pressed, this, &UStarInputComponent::OnJackPressed);
	PlayerInputComponent->BindKey(EKeys::Q, IE_Pressed, this, &UStarInputComponent::OnLeftLegPressed);
	PlayerInputComponent->BindKey(EKeys::Q, IE_Released, this, &UStarInputComponent::OnLeftLegReleased);
	PlayerInputComponent->BindKey(EKeys::E, IE_Pressed, this, &UStarInputComponent::OnRightLegPressed);
	PlayerInputComponent->BindKey(EKeys::E, IE_Released, this, &UStarInputComponent::OnRightLegReleased);
}

void UStarInputComponent::PressAction(EStarAction Action)
{
	AStarRunnerPawn* R = Runner();
	if (!R)
	{
		return;
	}
	if (R->HandleAction(Action, EStarPhase::Begin))
	{
		ActiveAction = Action;
	}
}

void UStarInputComponent::ReleaseAction(EStarAction Action)
{
	AStarRunnerPawn* R = Runner();
	if (!R)
	{
		return;
	}
	if (R->HandleAction(Action, EStarPhase::Complete))
	{
		ActiveAction = EStarAction::None;
	}
}

void UStarInputComponent::OnJumpLeftPressed()  { PressAction(EStarAction::JumpLeft); }
void UStarInputComponent::OnJumpRightPressed() { PressAction(EStarAction::JumpRight); }

void UStarInputComponent::OnSquatPressed()  { PressAction(EStarAction::Squat); }
void UStarInputComponent::OnSquatReleased() { ReleaseAction(EStarAction::Squat); }

void UStarInputComponent::OnLeftLegPressed()  { PressAction(EStarAction::LeftLeg); }
void UStarInputComponent::OnLeftLegReleased() { ReleaseAction(EStarAction::LeftLeg); }

void UStarInputComponent::OnRightLegPressed()  { PressAction(EStarAction::RightLeg); }
void UStarInputComponent::OnRightLegReleased() { ReleaseAction(EStarAction::RightLeg); }

void UStarInputComponent::OnJackPressed()
{
	// Tapping the key is a complete jumping-jack cycle: Begin now, Complete
	// when the arc lands. Emit Begin immediately; the runner's UpdateJump
	// drives the motion, and we complete the cycle right after so the next
	// action is not blocked.
	AStarRunnerPawn* R = Runner();
	if (!R)
	{
		return;
	}
	if (R->HandleAction(EStarAction::JumpingJack, EStarPhase::Begin))
	{
		R->HandleAction(EStarAction::JumpingJack, EStarPhase::Complete);
	}
}

// ---------------------------------------------------------------------------
// WebSocket gesture feed. Reserved for the gesture phase; keyboard works
// with this entirely disconnected.
// ---------------------------------------------------------------------------

void UStarInputComponent::ConnectGestures(const FString& WebSocketUrl)
{
	if (Socket.IsValid())
	{
		return;
	}
	Generation = NextGeneration();
	const FString Url = FString::Printf(TEXT("%s?generation=%llu"), *WebSocketUrl, Generation);
	GestureUrl = Url;

	Socket = FWebSocketsModule::Get().CreateWebSocket(Url, TEXT("ws"));
	Socket->OnConnected().AddUObject(this, &UStarInputComponent::OnWSConnected);
	Socket->OnConnectionError().AddUObject(this, &UStarInputComponent::OnWSError);
	Socket->OnMessage().AddUObject(this, &UStarInputComponent::OnWSMessage);
	Socket->OnClosed().AddUObject(this, &UStarInputComponent::OnWSClosed);
	Socket->Connect();
}

void UStarInputComponent::DisconnectGestures()
{
	if (Socket.IsValid())
	{
		Socket->OnConnected().RemoveAll(this);
		Socket->OnConnectionError().RemoveAll(this);
		Socket->OnMessage().RemoveAll(this);
		Socket->OnClosed().RemoveAll(this);
		Socket->Close();
		Socket.Reset();
	}
	bGesturesConnected = false;
}

void UStarInputComponent::OnWSConnected()
{
	bGesturesConnected = true;
}

void UStarInputComponent::OnWSError(const FString& Error)
{
	bGesturesConnected = false;
}

void UStarInputComponent::OnWSClosed(int32 StatusCode, const FString& Reason, bool bWasClean)
{
	bGesturesConnected = false;
}

void UStarInputComponent::OnWSMessage(const FString& Message)
{
	TSharedPtr<FJsonObject> Obj;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Message);
	if (!FJsonSerializer::Deserialize(Reader, Obj) || !Obj.IsValid())
	{
		return;
	}
	// Terminal error frame from the gateway: pause and re-ready with a new
	// generation; never replay the old cycle.
	if (Obj->HasField(TEXT("error")))
	{
		DisconnectGestures();
		return;
	}

	FStarInputEvent Event;
	FString GenString;
	const TSharedPtr<FJsonObject>* TrackingObj;
	const TSharedPtr<FJsonObject>* ActionObj;
	if (Obj->TryGetObjectField(TEXT("tracking"), TrackingObj))
	{
		(*TrackingObj)->TryGetStringField(TEXT("generation"), GenString);
		FString State;
		(*TrackingObj)->TryGetStringField(TEXT("state"), State);
		Event.Tracking = FStarInputEvent::TrackingFromString(State);
	}
	else if (Obj->TryGetObjectField(TEXT("action"), ActionObj))
	{
		(*ActionObj)->TryGetStringField(TEXT("generation"), GenString);
		FString A, P;
		(*ActionObj)->TryGetStringField(TEXT("action"), A);
		(*ActionObj)->TryGetStringField(TEXT("phase"), P);
		Event.Action = FStarInputEvent::ActionFromString(A);
		Event.Phase = FStarInputEvent::PhaseFromString(P);
	}
	else
	{
		return;
	}
	Event.Generation = FCString::Strtoui64(*GenString, nullptr, 10);
	HandleStreamEvent(Event);
}

void UStarInputComponent::HandleStreamEvent(const FStarInputEvent& Event)
{
	AStarRunnerPawn* R = Runner();
	if (!R)
	{
		return;
	}
	// Generation check (documented UE input check #1).
	if (Event.Generation != Generation)
	{
		return;
	}
	if (Event.IsTracking())
	{
		R->HandleTracking(Event.Tracking);
	}
	else if (Event.IsAction())
	{
		R->HandleAction(Event.Action, Event.Phase);
	}
}
